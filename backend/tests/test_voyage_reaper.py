"""The startup reaper must not leave a voyage stranded on "generating".

Phase 2 is what introduces micro_status / portrait_status == "generating", and
those rows have no owner but the daemon thread that set them. A restart
mid-stream — a deploy, an OOM, a worker recycle — kills that thread, and the
hub then polls GET /api/voyage every 2 s against a row nothing will ever move.
Worse than the analysis case: there is no error state for the person to see.

The cutoff carries the same reasoning as tests/test_stale_reaper.py, which
covers analyses and is not touched here: create_app() runs in every process
that opens this database, so an unfiltered sweep reaches voyages that are still
streaming.
"""
import logging
from datetime import datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

import app as app_module
from app import create_app, reap_stale_generating, STALE_RUN_CUTOFF_MINUTES
from app.extensions import db
from app.models.counselor_code import CounselorCode
from app.models.profile import Profile
from app.models.user import User
from app.models.voyage import Voyage
from app.services.voyage import bank
from flask_jwt_extended import create_access_token

OLD = STALE_RUN_CUTOFF_MINUTES + 5
YOUNG = 1


def _voyage(age_minutes: int, **statuses) -> Voyage:
    """One voyage whose updated_at is `age_minutes` old.

    updated_at is stamped at INSERT, never by a later write: the column's
    onupdate=datetime.utcnow would silently reset it to now and every age in
    this file with it.
    """
    user = User(email=f"r{uuid4().hex[:8]}@test.com", password_hash="x",
                role="candidate", plan="free")
    db.session.add(user)
    db.session.commit()
    row = Voyage(
        user_id=user.id,
        consent_at=datetime.utcnow(),
        age_attested=True,
        updated_at=datetime.utcnow() - timedelta(minutes=age_minutes),
        **statuses,
    )
    db.session.add(row)
    db.session.commit()
    return row


def _fresh(row: Voyage) -> Voyage:
    """The row as the database holds it — the sweep runs with
    synchronize_session=False, so the identity map is stale by design."""
    db.session.expire_all()
    return db.session.get(Voyage, row.id)


def test_a_phrase_orphaned_by_a_restart_is_reset(app):
    orphan = _voyage(OLD, micro_status="generating")

    assert reap_stale_generating() == 1
    assert _fresh(orphan).micro_status == "error"


def test_a_portrait_orphaned_by_a_restart_is_reset(app):
    """The two statuses are swept independently: a voyage may be stranded on
    either one on its own."""
    orphan = _voyage(OLD, portrait_status="generating")

    assert reap_stale_generating() == 1
    assert _fresh(orphan).portrait_status == "error"


def test_a_live_generation_is_left_alone(app):
    """The one that matters. create_app() runs in every process that opens this
    database — each gunicorn worker, `flask db upgrade` on deploy, every seed
    script — so a sweep with no age filter fires while someone's portrait is
    still streaming, and the hub shows an error for a run that then succeeds.
    """
    live = _voyage(YOUNG, micro_status="generating", portrait_status="generating")

    assert reap_stale_generating() == 0
    row = _fresh(live)
    assert row.micro_status == "generating"
    assert row.portrait_status == "generating"


def test_only_generating_rows_are_touched(app):
    """Every other value either status can hold, all of them old enough to be
    swept if the status filter were dropped."""
    settled = _voyage(OLD, micro_status="success", portrait_status="draft")
    validated = _voyage(OLD, micro_status="error", portrait_status="validated")
    untouched = _voyage(OLD)      # the defaults: "none" / "none"

    assert reap_stale_generating() == 0
    assert (_fresh(settled).micro_status, _fresh(settled).portrait_status) == \
        ("success", "draft")
    assert (_fresh(validated).micro_status, _fresh(validated).portrait_status) == \
        ("error", "validated")
    assert (_fresh(untouched).micro_status, _fresh(untouched).portrait_status) == \
        ("none", "none")


def test_both_statuses_on_one_row_are_reset_together(app):
    """One row, one statement. Sweeping the two statuses as two successive
    UPDATEs cannot work: the first bumps updated_at through the column's own
    onupdate, which pushes the row past the cutoff, and the second then matches
    nothing — leaving portrait_status stranded on exactly the value this reaps.
    """
    both = _voyage(OLD, micro_status="generating", portrait_status="generating")

    assert reap_stale_generating() == 1      # one row changed, not two statuses
    row = _fresh(both)
    assert row.micro_status == "error"
    assert row.portrait_status == "error"


def test_a_sweep_for_one_status_never_rewrites_the_other(app):
    """Both rows here MATCH — each is generating on one status — so the single
    UPDATE rewrites both columns on both of them. Each column must therefore be
    rewritten only where it actually reads "generating".

    Without that guard the phrase's orphan flips a portrait a counselor had
    already validated to "error", and the portrait's orphan erases a phrase the
    candidate can already see on the hub. Neither is visible in a test that
    only asserts the status it came for.
    """
    stranded_phrase = _voyage(OLD, micro_status="generating",
                              portrait_status="validated")
    stranded_portrait = _voyage(OLD, micro_status="success",
                                portrait_status="generating")

    assert reap_stale_generating() == 2
    assert _fresh(stranded_phrase).micro_status == "error"
    assert _fresh(stranded_phrase).portrait_status == "validated"
    assert _fresh(stranded_portrait).micro_status == "success"
    assert _fresh(stranded_portrait).portrait_status == "error"


def test_the_count_is_the_number_of_rows_reset(app):
    """What the startup log line reports, so it has to mean something: the
    stale rows, never the live one beside them."""
    _voyage(OLD, micro_status="generating")
    _voyage(OLD, portrait_status="generating")
    _voyage(YOUNG, micro_status="generating")
    _voyage(OLD, micro_status="success")

    assert reap_stale_generating() == 2


def test_a_reaped_row_is_given_no_invented_error(app):
    """Nothing was alive to observe this failure. The status is the signal, and
    a message here would claim knowledge of something nobody saw."""
    orphan = _voyage(OLD, micro_status="generating", portrait_status="generating")

    reap_stale_generating()
    row = _fresh(orphan)
    assert row.micro == {}
    assert row.portrait == {}
    assert row.micro_encrypted is None
    assert row.portrait_encrypted is None


def test_create_app_sweeps_the_voyages_on_startup():
    """The whole point: a restart is what strands these rows, so the sweep has
    to run on the way back up. Nothing else in the suite would notice the call
    being dropped from create_app().

    Patched rather than seeded: TestingConfig is sqlite:///:memory:, so the app
    this builds gets its own empty database and could never see a row. What
    carries the test is the trailing assert_called_once_with() — the body would
    pass just as happily if create_app() never called the sweep at all.

    reap_stale_running is deliberately NOT stubbed. It runs for real against
    that empty database, raises "no such table: analyses", and its own except
    swallows it; the sweep under test still has to be reached. That is the
    behaviour b2a6089 bought by giving each reaper its own try, so leaving it
    unstubbed keeps this test honest about the arrangement it runs in.
    """
    with patch.object(app_module, "reap_stale_generating", return_value=0) as reaper:
        create_app("testing")

    reaper.assert_called_once_with()


def test_a_failed_sweep_never_stops_the_server_coming_up():
    """First boot runs create_app() before `flask db upgrade` has made the
    voyages table — the same reason reap_stale_running() is wrapped.

    Two assertions, and both are needed: create_app() returning an app proves
    the exception was swallowed, and assert_called_once_with() proves there was
    an exception to swallow. Without the second, a create_app() that had
    silently stopped calling the sweep would sail through this.
    """
    with patch.object(app_module, "reap_stale_generating",
                      side_effect=RuntimeError("no such table: voyages")) as reaper:
        assert create_app("testing") is not None

    reaper.assert_called_once_with()


def test_a_failed_sweep_leaves_a_trace_in_the_log(caplog):
    """The swallow stays — booting must never depend on a sweep — but "DB not
    yet migrated on first boot" is the expected cause, not the only one, and a
    transient failure that logged nothing anywhere would be invisible.

    exc_info is the half that matters: the sentence alone says something went
    wrong, the exception says what, and only the second is diagnosable.
    """
    with caplog.at_level(logging.DEBUG):
        with patch.object(app_module, "reap_stale_generating",
                          side_effect=RuntimeError("no such table: voyages")):
            create_app("testing")

    hits = [r for r in caplog.records if "voyages sweep" in r.message]
    assert len(hits) == 1
    assert hits[0].levelno == logging.DEBUG
    assert hits[0].exc_info is not None


def test_the_cutoff_is_overridable_for_a_caller_that_knows_better(app):
    """Same signature as reap_stale_running(), so an admin script can sweep on
    its own terms."""
    recent = _voyage(YOUNG, micro_status="generating")

    assert reap_stale_generating(cutoff_minutes=0) == 1
    assert _fresh(recent).micro_status == "error"


def test_a_failing_analyses_sweep_does_not_skip_the_voyage_sweep():
    """The two sweeps had one try between them, so an error in the analyses
    sweep silently skipped the voyage sweep for that whole boot.

    That asymmetry matters: a stale analysis shows the candidate « L'analyse
    n'a pas abouti », while a stranded voyage has no error state at all — the
    hub just polls it for ever. They get one try each.
    """
    with patch.object(app_module, "reap_stale_running",
                      side_effect=RuntimeError("no such table: analyses")), \
            patch.object(app_module, "reap_stale_generating", return_value=0) as reaper:
        assert create_app("testing") is not None

    reaper.assert_called_once_with()


ALL_SESSIONS = ["0", "1", "2", "3", "4", "5"]


def _aged_player(email: str, **columns) -> tuple[str, dict, datetime]:
    """A candidate's voyage whose updated_at is well past the sweep's cutoff.

    Returns (voyage_id, auth headers, the stale timestamp). The age is written
    last, by a bulk UPDATE naming the column, so no later ORM write stamps it
    back to now.
    """
    user = User(email=email, password_hash="x", role="candidate", plan="free")
    db.session.add(user)
    db.session.commit()

    responses = columns.pop("responses", {"answers": {}, "billets": {}})
    voyage = Voyage(user_id=user.id, consent_at=datetime.utcnow(), age_attested=True,
                    **columns)
    voyage.responses = responses
    db.session.add(voyage)
    db.session.commit()
    voyage_id = voyage.id

    stale = datetime.utcnow() - timedelta(minutes=STALE_RUN_CUTOFF_MINUTES + 45)
    db.session.query(Voyage).filter_by(id=voyage_id).update(
        {"updated_at": stale}, synchronize_session=False)
    db.session.commit()

    token = create_access_token(identity=user.id)
    return voyage_id, {"Authorization": f"Bearer {token}"}, stale


def test_a_finished_voyage_can_no_longer_hide_its_portrait_by_re_saving_an_answer(app, client):
    """The phase-2 blind spot, narrowed.

    A `termine` voyage used to accept a re-saved session-0 answer: 200,
    updated_at moved past the cutoff, and a portrait stranded on "generating"
    left the sweep's reach. Every session of a finished voyage is complete and
    a completed session now refuses writes, so the same request is a 409, the
    clock stays where it was, and the sweep reaches the portrait.
    """
    voyage_id, headers, stale = _aged_player(
        "clock@test.com", status="termine", portrait_status="generating",
        sessions_completed=ALL_SESSIONS)

    item = bank.items("0")[0]
    res = client.put("/api/voyage/responses", headers=headers,
                     json={"answers": {item["id"]: True}})
    assert res.status_code == 409

    db.session.expire_all()
    assert db.session.get(Voyage, voyage_id).updated_at == stale

    assert reap_stale_generating() == 1
    db.session.expire_all()
    assert db.session.get(Voyage, voyage_id).portrait_status == "error"


def test_an_open_voyage_can_still_refresh_a_stranded_phrases_clock(app, client):
    """What remains of the blind spot. Documents it rather than asserting a
    guarantee.

    The phrase stranded on "generating" at session 0; the person has a code and
    a profile, so session 1 is open, and saving an S1 answer is a legitimate
    write. It moves updated_at, and the sweep stops seeing the row for as long
    as they keep playing. Their own way out meanwhile is
    POST /api/voyage/micro/retry.

    When per-run timestamps land, this should start failing on the last
    assertion — that is the signal to delete it.
    """
    code = CounselorCode(label="Cap Emploi test")
    db.session.add(code)
    db.session.commit()
    s0 = {item["id"]: True for item in bank.items("0")}
    voyage_id, headers, stale = _aged_player(
        "clock-open@test.com", status="s0_termine", micro_status="generating",
        sessions_completed=["0"], counselor_code_id=code.id,
        responses={"answers": s0, "billets": {}})
    user_id = db.session.get(Voyage, voyage_id).user_id
    db.session.add(Profile(user_id=user_id, prenom="Marie", tranche_age="25_34"))
    db.session.commit()
    db.session.expire_all()
    assert db.session.get(Voyage, voyage_id).updated_at == stale     # setup left the clock

    item = bank.items("1")[0]
    assert item["id"] not in s0          # a genuinely new answer, not a no-op re-send
    res = client.put("/api/voyage/responses", headers=headers,
                     json={"answers": {item["id"]: item["options"][0]["letter"]}})
    assert res.status_code == 200

    db.session.expire_all()
    saved = db.session.get(Voyage, voyage_id)
    assert saved.responses["answers"][item["id"]] == item["options"][0]["letter"]
    assert saved.updated_at > stale

    # And so the sweep no longer sees it.
    assert reap_stale_generating() == 0
    assert db.session.get(Voyage, voyage_id).micro_status == "generating"


def test_a_save_that_changes_nothing_no_longer_hides_a_finished_voyages_portrait(app, client):
    """The other half of the finished-voyage path, closed.

    A request naming no session (an empty body, only unknown ids) is not
    caught by the completed-session refusal. It used to re-encrypt the
    unchanged answers and commit anyway: 200, updated_at moved, and the
    stranded portrait left the sweep's reach. A save that changes nothing now
    writes nothing, so the clock stays where it was and the sweep reaches it.
    """
    for n, body in enumerate(({}, {"answers": {"S9-99": "Z"}})):
        voyage_id, headers, stale = _aged_player(
            f"clock-empty-{n}@test.com", status="termine", portrait_status="generating",
            sessions_completed=ALL_SESSIONS)

        res = client.put("/api/voyage/responses", headers=headers, json=body)
        assert res.status_code == 200

        db.session.expire_all()
        assert db.session.get(Voyage, voyage_id).updated_at == stale
        assert reap_stale_generating() == 1
        db.session.expire_all()
        assert db.session.get(Voyage, voyage_id).portrait_status == "error"

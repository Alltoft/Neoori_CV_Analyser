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
from datetime import datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

import app as app_module
from app import create_app, reap_stale_generating, STALE_RUN_CUTOFF_MINUTES
from app.extensions import db
from app.models.user import User
from app.models.voyage import Voyage

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
    this builds gets its own empty database and could never see a row.
    reap_stale_running is patched too, and not for tidiness — it shares this
    try block and runs first, so against that empty database it raises "no such
    table: analyses" and the sweep under test is never reached. Without this
    line the assertion below fails on correct code.
    """
    with patch.object(app_module, "reap_stale_running", return_value=0), \
            patch.object(app_module, "reap_stale_generating", return_value=0) as reaper:
        create_app("testing")

    reaper.assert_called_once_with()


def test_a_failed_sweep_never_stops_the_server_coming_up():
    """First boot runs create_app() before `flask db upgrade` has made the
    voyages table — the same reason reap_stale_running() is wrapped.

    reap_stale_running is stubbed to succeed so that the raise below is what
    the except clause actually catches; letting it fail first would make this
    test pass without ever calling the function it names.
    """
    with patch.object(app_module, "reap_stale_running", return_value=0), \
            patch.object(app_module, "reap_stale_generating",
                         side_effect=RuntimeError("no such table: voyages")) as reaper:
        assert create_app("testing") is not None

    reaper.assert_called_once_with()


def test_the_cutoff_is_overridable_for_a_caller_that_knows_better(app):
    """Same signature as reap_stale_running(), so an admin script can sweep on
    its own terms."""
    recent = _voyage(YOUNG, micro_status="generating")

    assert reap_stale_generating(cutoff_minutes=0) == 1
    assert _fresh(recent).micro_status == "error"

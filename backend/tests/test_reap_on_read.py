"""A run orphaned by a restart is reaped when its row is read (four-doors plan,
Ruling R30; spec decisions 27, 47 and 49).

The startup reaper only takes `running` rows older than STALE_RUN_CUTOFF_MINUTES:
every process that boots an app runs it, and a younger row may still be
streaming in another worker. A run orphaned by a deploy is a minute or two old
when the new container boots, so the sweep misses it, and the row reads
« running » until some later boot. « Relancer » (the counselor's only remedy,
decision 27) and the promo relaunch (decision 49) both need `error`, and a
no-login tab waits for a failure that never comes.

reap_if_orphaned() applies the startup rule to the one row a read is about to
serve. These tests pin that rule from the routes' side.
"""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import event
from sqlalchemy.orm.attributes import set_committed_value

import app as app_module
from app import STALE_RUN_CUTOFF_MINUTES
from app.extensions import db
from app.models.analysis import Analysis
from app.utils.tokens import hash_token, new_access_token
from tests.helpers_doors import bearer, counselor, user

BASE = "/api/counselor/analyses"
TOKEN = "X-Analysis-Token"

STALE = STALE_RUN_CUTOFF_MINUTES + 1      # minutes: just past the cutoff
DAYS = 24 * 60


def _ago(minutes: int) -> datetime:
    return datetime.utcnow() - timedelta(minutes=minutes)


def _run(status="running", *, started=None, created=None, **fields) -> Analysis:
    """An analysis row. `started` and `created` are minutes ago.

    started=None leaves started_at NULL, as on a row that went running before
    the column existed. created defaults to the moment the run started, which
    is where a first run's created_at sits.
    """
    if created is None:
        created = started if started is not None else 0
    row = Analysis(
        status=status, inputs={"_path": "1"},
        started_at=None if started is None else _ago(started),
        created_at=_ago(created), **fields,
    )
    db.session.add(row)
    db.session.commit()
    return row


def _account_run(owner, status="running", **timing) -> Analysis:
    return _run(status, user_id=owner.id, door="account", **timing)


def _advisor_run(c, status="running", **timing) -> Analysis:
    return _run(status, door="advisor", counselor_id=c.id, **timing)


def _no_login_run(status="running", **timing) -> tuple[str, Analysis]:
    token = new_access_token()
    return token, _run(status, door="anonymous", access_token_hash=hash_token(token), **timing)


def _poll(client, row, headers=None):
    return client.get(f"/api/analyses/{row.id}", headers=headers or {})


def _stored(analysis_id: str) -> str:
    """The status the database holds, not the one the session remembers.

    The test and the request share one session, so a change that was flushed
    but never committed would still read back. Rolling back first drops
    anything pending (and expires every loaded row), which is what makes this a
    check that the reap was committed.
    """
    db.session.rollback()
    return db.session.get(Analysis, analysis_id).status


# ── the three read routes ────────────────────────────────────────────────────

def test_a_run_past_the_cutoff_is_served_as_the_failure_it_is(client, app):
    owner = user()
    row = _account_run(owner, started=STALE)
    res = _poll(client, row, bearer(owner))
    assert res.status_code == 200
    assert res.get_json()["analysis"]["status"] == "error"
    assert _stored(row.id) == "error"


@pytest.mark.parametrize("timing", [
    dict(started=1),
    dict(started=STALE_RUN_CUTOFF_MINUTES - 1),
    # A relaunch re-runs a row created days ago: the run is the clock, not the row.
    dict(started=1, created=3 * DAYS),
], ids=["a minute in", "a minute short of the cutoff", "a relaunch of an old row"])
def test_a_run_inside_the_cutoff_is_left_alone(timing, client, app):
    """It may still be streaming in a worker that is alive."""
    owner = user()
    row = _account_run(owner, **timing)
    res = _poll(client, row, bearer(owner))
    assert res.status_code == 200
    assert res.get_json()["analysis"]["status"] == "running"
    assert _stored(row.id) == "running"


@pytest.mark.parametrize("status", ["queued", "success", "error", "timeout"])
def test_a_row_that_is_not_running_is_never_reaped(status, client, app):
    """`queued` is the one that matters: a relaunch or an unlock queues the row
    again while started_at still holds the PREVIOUS run's time, so reaping it
    would kill every fresh relaunch. The finished states must stay as they are
    too — `timeout` is not `error`, and a report is not a failure."""
    owner = user()
    row = _account_run(owner, status, started=2 * DAYS, created=3 * DAYS)
    res = _poll(client, row, bearer(owner))
    assert res.status_code == 200
    assert res.get_json()["analysis"]["status"] == status
    assert _stored(row.id) == status


def test_a_row_with_no_started_at_is_aged_by_created_at(client, app):
    """The startup reaper's fallback, for rows that went running before the
    column existed."""
    owner = user()
    old = _account_run(owner, started=None, created=STALE)
    recent = _account_run(owner, started=None, created=1)
    assert _poll(client, old, bearer(owner)).get_json()["analysis"]["status"] == "error"
    assert _poll(client, recent, bearer(owner)).get_json()["analysis"]["status"] == "running"
    assert (_stored(old.id), _stored(recent.id)) == ("error", "running")


def test_a_stale_no_login_report_is_reaped_when_read_by_its_token(client, app):
    token, row = _no_login_run(started=STALE)
    res = client.get("/api/analyses/by-token", headers={TOKEN: token})
    assert res.status_code == 200
    assert res.get_json()["analysis"]["status"] == "error"
    assert _stored(row.id) == "error"


@patch("app.routes.counselor_space.start_analysis")
def test_a_counselor_reads_a_stale_report_and_can_then_relaunch_it(start, client, app):
    c = counselor()
    row = _advisor_run(c, started=STALE)
    headers = bearer(c)

    # « running » is not a failure, so the relaunch refuses it ...
    assert client.post(f"{BASE}/{row.id}/relaunch", headers=headers).status_code == 409
    start.assert_not_called()

    # ... until the counselor's page reads the row.
    res = client.get(f"{BASE}/{row.id}", headers=headers)
    assert res.status_code == 200
    assert res.get_json()["analysis"]["status"] == "error"
    assert _stored(row.id) == "error"

    res = client.post(f"{BASE}/{row.id}/relaunch", headers=headers)
    assert res.status_code == 200
    assert res.get_json()["analysis"]["status"] == "queued"
    start.assert_called_once()


@patch("app.routes.analyses.start_analysis")
def test_a_promo_run_can_be_relaunched_once_its_owner_has_read_it(start, client, app):
    """Decision 49: the same dead end as the counselor's, for the account."""
    owner = user()
    row = _run(user_id=owner.id, door="promo", started=STALE)
    headers = bearer(owner)

    assert client.post(f"/api/analyses/{row.id}/relaunch", headers=headers).status_code == 409
    assert _poll(client, row, headers).get_json()["analysis"]["status"] == "error"

    res = client.post(f"/api/analyses/{row.id}/relaunch", headers=headers)
    assert res.status_code == 200
    assert res.get_json()["analysis"]["status"] == "queued"
    start.assert_called_once()


def test_only_the_row_being_read_is_reaped(client, app):
    owner = user()
    read, unread = _account_run(owner, started=STALE), _account_run(owner, started=STALE)
    assert _poll(client, read, bearer(owner)).get_json()["analysis"]["status"] == "error"
    assert (_stored(read.id), _stored(unread.id)) == ("error", "running")


# ── a reap sends nothing ─────────────────────────────────────────────────────

def test_no_mail_leaves_when_a_run_is_reaped(client, app):
    """CLAUDE.md « Mails transactionnels »: a run orphaned by a restart sends
    nothing. The key is set and Resend is the mock, so a mail from any path —
    _notify_outcome or a direct call — would land on it."""
    app.config["RESEND_API_KEY"] = "re_test"
    owner, c = user(), counselor()
    token, _ = _no_login_run(started=STALE)
    account, advisor = _account_run(owner, started=STALE), _advisor_run(c, started=STALE)

    with patch("app.services.email_service.resend.Emails.send") as sent, \
            patch("app.services.anthropic_service._notify_outcome") as notified:
        reads = [
            _poll(client, account, bearer(owner)),
            client.get("/api/analyses/by-token", headers={TOKEN: token}),
            client.get(f"{BASE}/{advisor.id}", headers=bearer(c)),
        ]
    # The reads did reap: without it, « nothing was sent » proves nothing.
    assert [r.get_json()["analysis"]["status"] for r in reads] == ["error"] * 3
    sent.assert_not_called()
    notified.assert_not_called()


# ── what a caller who may not read the row cannot do ─────────────────────────

def test_a_row_the_caller_may_not_read_is_neither_served_nor_reaped(client, app):
    """The reap comes after the access check on every route: a request that is
    refused must not change the row either."""
    owner, other, c = user(), user("autre@test.fr"), counselor()
    mine = _account_run(owner, started=STALE)
    _, no_login = _no_login_run(started=STALE)
    advisor = _advisor_run(c, started=STALE)
    # An advisor row is closed to the candidate routes even when it somehow
    # holds a token (ruling 2): /by-token reaches _may_access and stops there.
    advisor_token = new_access_token()
    advisor_with_hash = _run(
        door="advisor", counselor_id=c.id, access_token_hash=hash_token(advisor_token), started=STALE,
    )

    refused = [
        (_poll(client, mine, bearer(other)), 403),                              # another owner
        (_poll(client, mine), 403),                                             # signed out
        (_poll(client, no_login, {TOKEN: "wrong"}), 403),                       # wrong key
        (client.get("/api/analyses/by-token", headers={TOKEN: "wrong"}), 404),
        (_poll(client, advisor, bearer(c)), 403),                               # the counselor's report, by the candidate route
        (client.get("/api/analyses/by-token", headers={TOKEN: advisor_token}), 404),
        (client.get(f"{BASE}/{advisor.id}", headers=bearer(counselor("autre-c@test.fr"))), 404),
        (client.get(f"{BASE}/{mine.id}", headers=bearer(c)), 404),              # not an advisor-door row
    ]
    for res, status in refused:
        assert res.status_code == status
        assert "analysis" not in res.get_json()
    for row in (mine, no_login, advisor, advisor_with_hash):
        assert _stored(row.id) == "running"


# ── the helper itself ────────────────────────────────────────────────────────

def test_reap_if_orphaned_says_what_it_did(app):
    stale, live = _account_run(user(), started=STALE), _account_run(user("autre@test.fr"), started=1)
    assert app_module.reap_if_orphaned(stale) is True
    assert app_module.reap_if_orphaned(live) is False
    # A second look at a reaped row finds a failure, not an orphan.
    assert app_module.reap_if_orphaned(stale) is False
    assert (_stored(stale.id), _stored(live.id)) == ("error", "running")


@pytest.mark.parametrize("timing,orphaned", [
    (dict(started=STALE), True),
    (dict(started=1), False),
    (dict(started=1, created=3 * DAYS), False),
    (dict(started=None, created=STALE), True),
    (dict(started=None, created=1), False),
    (dict(status="queued", started=2 * DAYS, created=3 * DAYS), False),
    (dict(status="success", started=2 * DAYS, created=3 * DAYS), False),
], ids=["stale", "fresh", "relaunch of an old row", "no started_at, old",
        "no started_at, recent", "queued with an old started_at", "success"])
def test_the_read_and_the_startup_reaper_apply_one_rule(timing, orphaned, app):
    """Each reaper gets its own row of the same shape, one after the other: a
    shared sweep would take both rows and let a miss by the read-time reaper go
    unseen. Both must give the verdict the startup rule gives."""
    startup_row = _run(**timing)
    assert (app_module.reap_stale_running() == 1) is orphaned

    read_row = _run(**timing)
    assert app_module.reap_if_orphaned(read_row) is orphaned
    assert _stored(read_row.id) == _stored(startup_row.id)


def test_a_run_that_finishes_after_it_was_read_is_not_overwritten(app):
    """The check and the write are one conditional UPDATE. A row loaded as
    `running` whose thread then wrote `success` must stay `success`: setting
    the status on the object would put `error` over a finished report."""
    row = _account_run(user(), started=STALE)
    # The thread's write lands after the request read the row: the row object
    # in the session still says `running`, as the route's copy does.
    Analysis.query.filter_by(id=row.id).update({"status": "success"}, synchronize_session=False)
    db.session.commit()
    set_committed_value(row, "status", "running")
    assert row.status == "running"

    assert app_module.reap_if_orphaned(row) is False
    assert _stored(row.id) == "success"


@pytest.mark.parametrize("status", ["success", "queued"])
def test_reading_a_row_that_is_not_running_issues_no_write(status, client, app):
    """Most reads are of a finished report: they must not touch the write path."""
    owner = user()
    row = _account_run(owner, status, started=2 * DAYS, created=3 * DAYS)
    seen = []

    def record(conn, cursor, statement, *rest):
        seen.append(statement)

    event.listen(db.engine, "before_cursor_execute", record)
    try:
        assert _poll(client, row, bearer(owner)).status_code == 200
    finally:
        event.remove(db.engine, "before_cursor_execute", record)

    assert seen                                       # the probe saw the request
    writes = [s for s in seen if s.lstrip().upper().startswith(("UPDATE", "INSERT", "DELETE"))]
    assert writes == []

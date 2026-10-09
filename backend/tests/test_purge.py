"""flask purge-expired (four-doors spec, decision 46)."""
from datetime import datetime, timedelta

from app.extensions import db
from app.models.analysis import Analysis
from app.models.counselor_note import CounselorNote
from app.models.price_feedback import BUCKETS, PriceFeedback
from app.models.run_log import RunLog
from app.services import purge
from tests.helpers_doors import counselor, user


def _ago(**delta):
    return datetime.utcnow() - timedelta(**delta)


def _row(**fields):
    row = Analysis(inputs={}, **({"status": "success"} | fields))
    db.session.add(row)
    db.session.commit()
    return row


def _hash(ch):
    return ch * 64


def test_it_takes_exactly_the_expired_kinds_and_nothing_else(app):
    c, u = counselor(), user()
    expired = [
        _row(status="draft", access_token_hash=_hash("a"), created_at=_ago(hours=49)),
        _row(door="anonymous", access_token_hash=_hash("b"), created_at=_ago(days=31)),
        _row(door="advisor", counselor_id=c.id, created_at=_ago(days=366)),
    ]
    kept = [
        _row(status="draft", access_token_hash=_hash("c"), created_at=_ago(hours=47)),
        _row(door="anonymous", access_token_hash=_hash("d"), created_at=_ago(days=29)),
        _row(door="anonymous", user_id=u.id, created_at=_ago(days=90)),      # claimed
        _row(door="legacy", created_at=_ago(days=400)),
        _row(door="account", user_id=u.id, created_at=_ago(days=400)),
        _row(status="draft", user_id=u.id, created_at=_ago(days=400)),       # owned draft
        _row(door="advisor", counselor_id=c.id, created_at=_ago(days=364)),
    ]
    db.session.add(CounselorNote(analysis_id=expired[2].id, counselor_id=c.id, body="n"))
    db.session.add(PriceFeedback(analysis_id=expired[1].id, bucket=BUCKETS[0]))
    db.session.add_all([RunLog(door="anonymous", created_at=_ago(days=3)), RunLog(door="anonymous")])
    db.session.commit()

    assert purge.run(apply=True) == {"held_drafts": 1, "anonymous": 1, "advisor": 1, "run_log": 1}
    assert {a.id for a in Analysis.query.all()} == {a.id for a in kept}
    assert CounselorNote.query.count() == 0 and PriceFeedback.query.count() == 0
    assert RunLog.query.count() == 1
    assert purge.run(apply=True) == {"held_drafts": 0, "anonymous": 0, "advisor": 0, "run_log": 0}


def test_a_dry_run_changes_nothing(app):
    _row(door="anonymous", access_token_hash=_hash("e"), created_at=_ago(days=31))
    assert purge.run(apply=False)["anonymous"] == 1
    assert Analysis.query.count() == 1


def test_before_rollback_takes_every_row_the_old_image_would_expose(app):
    c, u = counselor(), user()
    _row(door="advisor", counselor_id=c.id)
    _row(door="anonymous", access_token_hash=_hash("f"))
    _row(status="draft", access_token_hash=_hash("g"))
    claimed = _row(door="anonymous", user_id=u.id)
    legacy = _row(door="legacy")
    counts = purge.run(apply=True, before_rollback=True)
    assert counts == {"held_drafts": 1, "anonymous": 1, "advisor": 1}
    assert {a.id for a in Analysis.query.all()} == {claimed.id, legacy.id}


def test_the_command(app):
    runner = app.test_cli_runner()
    result = runner.invoke(args=["purge-expired", "--dry-run"])
    assert result.exit_code == 0 and "dry run" in result.output
    result = runner.invoke(args=["purge-expired", "--before-rollback"])
    assert result.exit_code == 0 and "dry run" in result.output

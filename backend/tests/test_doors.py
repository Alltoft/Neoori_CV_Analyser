"""The four doors, as a table (four-doors spec, « Submit, per door »)."""
from datetime import datetime, timedelta

import pytest

from app.extensions import db
from app.models.analysis import Analysis
from app.models.run_log import RunLog
from app.services import doors


@pytest.mark.parametrize("door,tier,code_kind,folds,consent,identity,token", [
    ("account",   "free", None,         True,  False, False, False),
    ("promo",     "paid", "promo",      True,  False, False, False),
    ("advisor",   "paid", "conseiller", False, True,  True,  False),
    ("anonymous", "free", None,         False, True,  False, True),
])
def test_the_table(door, tier, code_kind, folds, consent, identity, token):
    plan = doors.PLANS[door]
    assert (plan.tier, plan.code_kind, plan.folds_profile, plan.needs_consent,
            plan.needs_identity, plan.gives_token) == (tier, code_kind, folds, consent, identity, token)
    assert plan.always_new_row is (door == "advisor")


@pytest.mark.parametrize("door,user_id,expected", [
    ("account", "u1", None), ("account", None, (doors.SIGN_IN, 401)),
    ("promo", "u1", None), ("promo", None, (doors.SIGN_IN, 401)),
    ("advisor", "u1", None), ("advisor", None, None),
    ("anonymous", None, None), ("anonymous", "u1", (doors.SIGNED_IN, 400)),
    ("premium", "u1", (doors.UNKNOWN, 400)), (["account"], "u1", (doors.UNKNOWN, 400)),
])
def test_decide(door, user_id, expected):
    plan, refusal = doors.decide(door, user_id=user_id)
    assert refusal == expected
    assert (plan is None) == (expected is not None)


def test_no_door_while_signed_in_means_the_account_door():
    # A stale tab posting {inputs, tier}: the free tier, never the tier it asked for.
    plan, refusal = doors.decide(None, user_id="u1")
    assert refusal is None and plan.door == "account" and plan.tier == "free"


def test_no_door_while_signed_out_is_unknown():
    assert doors.decide(None, user_id=None) == (None, (doors.UNKNOWN, 400))


def _log(door, user_id=None, hours_ago=0):
    db.session.add(RunLog(door=door, user_id=user_id,
                          created_at=datetime.utcnow() - timedelta(hours=hours_ago)))


def test_the_account_cap_counts_the_last_24_hours_of_this_account(app):
    for _ in range(5):
        _log("account", "u1")
    _log("account", "u1", hours_ago=25)
    _log("account", "u2")
    db.session.commit()
    plan = doors.PLANS["account"]
    assert doors.over_cap(plan, "u1") == doors.ACCOUNT_CAP.format(n=5)
    assert doors.over_cap(plan, "u2") is None


def test_deleting_reports_never_lowers_the_count(app):
    """Blocker B1 of the spec review: the count reads run_log, not analyses."""
    for _ in range(5):
        _log("account", "u1")
        db.session.add(Analysis(user_id=None, status="success", inputs={}))
    db.session.commit()
    Analysis.query.delete()
    db.session.commit()
    assert doors.over_cap(doors.PLANS["account"], "u1") is not None


def test_the_anonymous_cap_counts_every_no_login_run(app):
    app.config["ANONYMOUS_RUNS_PER_DAY"] = 3
    for _ in range(3):
        _log("anonymous")
    db.session.commit()
    assert doors.over_cap(doors.PLANS["anonymous"], None) == doors.ANONYMOUS_CAP


def test_promo_and_advisor_have_no_daily_cap(app):
    for _ in range(50):
        _log("promo", "u1")
        _log("advisor")
    db.session.commit()
    assert doors.over_cap(doors.PLANS["promo"], "u1") is None
    assert doors.over_cap(doors.PLANS["advisor"], None) is None

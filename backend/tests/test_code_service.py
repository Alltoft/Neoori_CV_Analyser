"""The three refusals and the log, tested away from any route.

Both call sites redeem through this module, so a rule proved once here holds
for an analysis unlock and a voyage unlock alike.
"""
from datetime import datetime, timedelta

from app.extensions import db
from app.models.code_redemption import CodeRedemption
from app.models.counselor_code import CounselorCode
from app.services import code_service


def _code(**kwargs):
    c = CounselorCode(label=kwargs.pop("label", "Cap Emploi test"), **kwargs)
    db.session.add(c)
    db.session.commit()
    return c


def test_normalize_accepts_spacing_and_case(app):
    assert code_service.normalize(" ab12-cd34 ") == "AB12CD34"
    assert code_service.normalize(None) == ""
    assert code_service.normalize(["nope"]) == ""


def test_resolve_returns_an_active_code(app):
    c = _code()
    found, refusal = code_service.resolve(c.code, "analysis")
    assert refusal is None
    assert found.id == c.id


def test_resolve_refuses_an_inactive_code(app):
    c = _code(is_active=False)
    found, refusal = code_service.resolve(c.code, "analysis")
    assert found is None
    assert refusal == code_service.INVALID


def test_resolve_refuses_a_revoked_code(app):
    c = _code(revoked_at=datetime.utcnow())
    found, refusal = code_service.resolve(c.code, "analysis")
    assert found is None
    assert refusal == code_service.INVALID


def test_resolve_refuses_an_expired_code(app):
    c = _code(expires_at=datetime.utcnow() - timedelta(days=1))
    found, refusal = code_service.resolve(c.code, "analysis")
    assert found is None
    assert refusal == code_service.EXPIRED


def test_resolve_refuses_an_exhausted_code(app):
    c = _code(max_uses=1)
    db.session.add(CodeRedemption(code_id=c.id, target_type="analysis", target_id="a-1"))
    db.session.commit()

    found, refusal = code_service.resolve(c.code, "analysis")
    assert found is None
    assert refusal == code_service.EXHAUSTED


def test_a_legacy_code_is_never_exhausted(app):
    """max_uses NULL = illimité. Rows written before this feature carry a
    uses_count with no redemption rows behind it; the count check never runs
    on them, so that history cannot lock anybody out."""
    c = _code(uses_count=97)
    found, refusal = code_service.resolve(c.code, "analysis")
    assert refusal is None
    assert found.id == c.id


def test_resolve_ignores_a_drifted_uses_count(app):
    """The reason resolve() counts rows instead of reading uses_count: that
    column is an increment that can drift, and a code whose counter ran ahead
    of its real redemptions must still work."""
    c = _code(max_uses=3, uses_count=97)
    db.session.add(CodeRedemption(code_id=c.id, target_type="analysis", target_id="a-1"))
    db.session.commit()

    found, refusal = code_service.resolve(c.code, "analysis")
    assert refusal is None
    assert found.id == c.id


def test_redeem_writes_the_row_and_bumps_the_counter(app):
    c = _code()
    assert code_service.redeem(c, user_id=None, target_type="analysis", target_id="a-1") is None

    row = CodeRedemption.query.filter_by(code_id=c.id).one()
    assert row.user_id is None
    assert row.target_type == "analysis"
    assert row.target_id == "a-1"
    assert c.uses_count == 1
    assert code_service.redemption_count(c.id) == 1


def test_use_counts_by_kind_groups_per_code_and_per_kind(app):
    a, b, unused, other = _code(), _code(), _code(), _code()
    db.session.add_all([
        CodeRedemption(code_id=a.id, target_type="analysis", target_id="a-1"),
        CodeRedemption(code_id=a.id, target_type="analysis", target_id="a-2"),
        CodeRedemption(code_id=a.id, target_type="voyage", target_id="v-1"),
        CodeRedemption(code_id=b.id, target_type="voyage", target_id="v-2"),
        CodeRedemption(code_id=other.id, target_type="analysis", target_id="a-3"),
    ])
    db.session.commit()

    counts = code_service.use_counts_by_kind([a.id, b.id, unused.id])
    assert counts == {
        a.id: {"analysis": 2, "voyage": 1},
        b.id: {"analysis": 0, "voyage": 1},
    }
    # A code nobody used is simply absent, and so is one it was not asked about:
    # callers default the missing ones to no uses.
    assert unused.id not in counts and other.id not in counts


def test_use_counts_by_kind_of_no_codes_is_empty(app):
    assert code_service.use_counts_by_kind([]) == {}

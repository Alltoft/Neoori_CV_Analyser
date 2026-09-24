"""The three schema changes, pinned at the model level.

Two of these tests are about what must NOT change: an existing counselor code
keeps working untouched, and a redemption outlives the person it belonged to.
"""
import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.code_redemption import CodeRedemption
from app.models.counselor_code import CounselorCode
from app.models.counselor_profile import CounselorProfile
from app.models.user import User


def _user(email="conseiller@test.com", role="candidate"):
    u = User(email=email, password_hash="x", role=role)
    db.session.add(u)
    db.session.commit()
    return u


def _code(**kwargs):
    c = CounselorCode(label=kwargs.pop("label", "Cap Emploi test"), **kwargs)
    db.session.add(c)
    db.session.commit()
    return c


def test_profile_starts_pending_with_no_limits(app):
    u = _user()
    p = CounselorProfile(
        user_id=u.id,
        structure="Cap Emploi 31",
        fonction="Conseillère en insertion",
        telephone="0561000000",
    )
    db.session.add(p)
    db.session.commit()

    assert p.status == "pending"
    assert p.max_codes is None            # NULL = illimité, decision 4
    assert p.max_uses_per_code is None
    assert p.reviewed_at is None
    assert p.decision_reason is None


def test_one_demande_per_account(app):
    u = _user()
    db.session.add(CounselorProfile(user_id=u.id, structure="a", fonction="b", telephone="c"))
    db.session.commit()

    db.session.add(CounselorProfile(user_id=u.id, structure="d", fonction="e", telephone="f"))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_an_existing_code_is_unowned_and_unlimited(app):
    """Decision 13: every row that exists today keeps behaving exactly as it did."""
    c = _code()
    assert c.owner_id is None
    assert c.max_uses is None
    assert c.expires_at is None
    assert c.revoked_at is None


def test_a_redemption_is_unique_per_target(app):
    c = _code()
    db.session.add(CodeRedemption(code_id=c.id, target_type="analysis", target_id="a-1"))
    db.session.commit()

    db.session.add(CodeRedemption(code_id=c.id, target_type="analysis", target_id="a-1"))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_a_redemption_outlives_the_person(app):
    """RGPD: erasing an account anonymises the row, it does not delete the count."""
    u = _user("beneficiaire@test.com")
    c = _code()
    r = CodeRedemption(code_id=c.id, user_id=u.id, target_type="voyage", target_id="v-1")
    db.session.add(r)
    db.session.commit()

    db.session.delete(u)
    db.session.commit()
    db.session.refresh(r)
    assert r.user_id is None

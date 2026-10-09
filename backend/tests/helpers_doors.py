"""Factories the four-doors tests share (four-doors spec)."""
from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import patch

from flask_jwt_extended import create_access_token

from app.extensions import db
from app.models.code_redemption import CodeRedemption
from app.models.counselor_code import CounselorCode
from app.models.counselor_profile import CounselorProfile
from app.models.user import User
from app.services import code_service

# Parcours 1 inputs create_analysis accepts: chemin A (the default) needs a
# target of at least 50 characters.
P1_INPUTS = {
    "cv_text": "c" * 300,
    "cible_visee": "Chauffeur livreur PL dans une entreprise de transport régional",
}


def user(email="marie@test.fr", role="candidate", verified=True):
    u = User(
        email=email, password_hash="x", role=role,
        email_verified_at=datetime.utcnow() if verified else None,
    )
    db.session.add(u)
    db.session.commit()
    return u


def bearer(u):
    token = create_access_token(identity=str(u.id), additional_claims={"role": u.role})
    return {"Authorization": f"Bearer {token}"}


def expired_bearer(u):
    """A token that lapsed: the access cookie outlives the JWT inside it."""
    token = create_access_token(
        identity=str(u.id), additional_claims={"role": u.role},
        expires_delta=timedelta(seconds=-30),
    )
    return {"Authorization": f"Bearer {token}"}


def counselor(email="conseil@test.fr", status="approved"):
    """A conseiller account. role follows status, as admin._decide keeps it."""
    u = user(email, role="counselor" if status == "approved" else "candidate")
    db.session.add(CounselorProfile(
        user_id=u.id, structure="s", fonction="f", telephone="t", status=status,
    ))
    db.session.commit()
    return u


def code(owner=None, *, max_uses=None, label="Atelier mardi", value="ABCD1234", expires_at=None):
    """owner=None is an admin-minted code — a promo code (spec decision 17)."""
    c = CounselorCode(
        label=label, owner_id=owner.id if owner else None,
        max_uses=max_uses, code=value, expires_at=expires_at,
    )
    db.session.add(c)
    db.session.commit()
    return c


@contextmanager
def stale_first_count_after_resolve():
    """The first redemption_count after resolve() is redeem()'s own read, and
    it reports 0 — as a MySQL snapshot older than another request's commit
    would. `served` says the stale read really happened."""
    real_resolve, real_count = code_service.resolve, code_service.redemption_count
    state = {"next": False, "served": False}

    def resolve_then_go_stale(code_str, target_type):
        found = real_resolve(code_str, target_type)
        state["next"] = True
        return found

    def count(code_id, target_type=None):
        if state["next"]:
            state["next"], state["served"] = False, True
            return 0
        return real_count(code_id, target_type)

    with patch.object(code_service, "resolve", side_effect=resolve_then_go_stale), \
            patch.object(code_service, "redemption_count", side_effect=count):
        yield state


@contextmanager
def last_place_goes_after_resolve(code_id, target_type):
    """Another request takes slot 1 after this one's check and before its
    write: resolve() said yes, redeem() will find the code full."""
    real_resolve = code_service.resolve

    def resolve_then_lose_the_place(code_str, kind):
        found = real_resolve(code_str, kind)
        db.session.add(CodeRedemption(
            code_id=code_id, target_type=target_type, target_id="x-other", slot=1,
        ))
        db.session.commit()
        return found

    with patch.object(code_service, "resolve", side_effect=resolve_then_lose_the_place):
        yield

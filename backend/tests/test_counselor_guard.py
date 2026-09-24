"""The guard that reads the DB, not only the claim.

role_required checks get_jwt()["role"], which outlives a revocation by up to
JWT_ACCESS_TOKEN_EXPIRES (1 h). A revoked conseiller holding a valid token must
be refused on the next request, not on the next hour.
"""
import pytest
from flask import Flask, jsonify
from flask_jwt_extended import create_access_token

from app.extensions import db
from app.models.counselor_profile import CounselorProfile
from app.models.user import User
from app.utils.decorators import approved_counselor_required


@pytest.fixture
def guarded(app):
    """Mount a throwaway route carrying only the decorator under test."""
    @app.route("/api/_guarded")
    @approved_counselor_required
    def _guarded():
        return jsonify({"ok": True}), 200
    return app


def _user_with(status, role="counselor", email="c@test.com"):
    u = User(email=email, password_hash="x", role=role)
    db.session.add(u)
    db.session.commit()
    if status is not None:
        db.session.add(CounselorProfile(
            user_id=u.id, structure="s", fonction="f", telephone="t", status=status,
        ))
        db.session.commit()
    token = create_access_token(identity=str(u.id), additional_claims={"role": role})
    return {"Authorization": f"Bearer {token}"}


def test_approved_counselor_passes(guarded):
    headers = _user_with("approved")
    assert guarded.test_client().get("/api/_guarded", headers=headers).status_code == 200


def test_admin_passes_without_a_profile(guarded):
    headers = _user_with(None, role="admin", email="a@test.com")
    assert guarded.test_client().get("/api/_guarded", headers=headers).status_code == 200


def test_candidate_is_refused(guarded):
    headers = _user_with(None, role="candidate", email="p@test.com")
    assert guarded.test_client().get("/api/_guarded", headers=headers).status_code == 403


def test_pending_is_refused_even_with_a_counselor_claim(guarded):
    headers = _user_with("pending")
    assert guarded.test_client().get("/api/_guarded", headers=headers).status_code == 403


def test_revoked_is_refused_before_the_token_expires(guarded):
    """The token still says counselor. The DB no longer does."""
    headers = _user_with("revoked")
    assert guarded.test_client().get("/api/_guarded", headers=headers).status_code == 403

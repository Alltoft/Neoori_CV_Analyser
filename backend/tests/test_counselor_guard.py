"""The guards read the DB, not the claim.

The access token's role claim is a snapshot from when it was minted, and it
lives up to JWT_ACCESS_TOKEN_EXPIRES (1 h). Both directions of a role change
must bite on the next request: a revoked conseiller refused, a newly approved
one let in — without signing out and back in.
"""
import pytest
from flask import Flask, jsonify
from flask_jwt_extended import create_access_token

from app.extensions import db
from app.models.counselor_profile import CounselorProfile
from app.models.user import User
from app.utils.decorators import approved_counselor_required, role_required


@pytest.fixture
def guarded(app):
    """Mount a throwaway route carrying only the decorator under test."""
    @app.route("/api/_guarded")
    @approved_counselor_required
    def _guarded():
        return jsonify({"ok": True}), 200
    return app


@pytest.fixture
def role_guarded(app):
    """Same, for role_required — what the /api/voyage/c/<token> routes carry."""
    @app.route("/api/_role_guarded")
    @role_required("counselor", "admin")
    def _role_guarded():
        return jsonify({"ok": True}), 200
    return app


def _user_with(status, role="counselor", email="c@test.com", claim=None):
    """A user whose row says `role`, holding a token whose claim says `claim`
    (the same as the row unless told otherwise)."""
    u = User(email=email, password_hash="x", role=role)
    db.session.add(u)
    db.session.commit()
    if status is not None:
        db.session.add(CounselorProfile(
            user_id=u.id, structure="s", fonction="f", telephone="t", status=status,
        ))
        db.session.commit()
    token = create_access_token(identity=str(u.id), additional_claims={"role": claim or role})
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


def test_approved_passes_on_the_candidate_token_it_applied_with(guarded):
    """Approval flipped the row. The token was minted before it."""
    headers = _user_with("approved", claim="candidate")
    assert guarded.test_client().get("/api/_guarded", headers=headers).status_code == 200


def test_a_candidate_row_is_refused_whatever_the_claim(guarded):
    headers = _user_with(None, role="candidate", email="p@test.com", claim="admin")
    assert guarded.test_client().get("/api/_guarded", headers=headers).status_code == 403


def test_role_required_lets_in_a_conseiller_approved_after_the_token(role_guarded):
    headers = _user_with("approved", claim="candidate")
    assert role_guarded.test_client().get("/api/_role_guarded", headers=headers).status_code == 200


def test_role_required_refuses_a_role_taken_back_after_the_token(role_guarded):
    headers = _user_with("revoked", role="candidate", claim="counselor")
    assert role_guarded.test_client().get("/api/_role_guarded", headers=headers).status_code == 403


def test_role_required_refuses_a_token_whose_user_is_gone(role_guarded):
    headers = _user_with("approved")
    CounselorProfile.query.delete()
    User.query.delete()
    db.session.commit()
    assert role_guarded.test_client().get("/api/_role_guarded", headers=headers).status_code == 403

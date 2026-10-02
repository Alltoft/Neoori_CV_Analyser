"""Approval is the only thing that grants the counselor role, and revocation
is the only thing that takes it back."""
from datetime import datetime
from unittest.mock import patch

import pytest
from flask_jwt_extended import create_access_token, create_refresh_token

from app.extensions import db
from app.models.counselor_profile import CounselorProfile
from app.models.user import User
from app.utils.auth_links import password_fingerprint


def _demande(email="conseiller@test.com", status="pending"):
    # Verified: a demande reaches the queue only once its address is proven.
    u = User(email=email, password_hash="x", role="candidate", email_verified_at=datetime.utcnow())
    db.session.add(u)
    db.session.commit()
    p = CounselorProfile(
        user_id=u.id,
        structure="Cap Emploi 31",
        fonction="Conseillère",
        telephone="0561000000",
        status=status,
    )
    db.session.add(p)
    db.session.commit()
    return u, p


def test_the_queue_lists_pending_demandes_with_their_account(client, admin_headers):
    _demande()
    r = client.get("/api/admin/counselor-applications?status=pending", headers=admin_headers)
    assert r.status_code == 200
    rows = r.get_json()["applications"]
    assert len(rows) == 1
    assert rows[0]["structure"] == "Cap Emploi 31"
    assert rows[0]["user"]["email"] == "conseiller@test.com"


def test_the_queue_is_admin_only(client, app):
    r = client.get("/api/admin/counselor-applications")
    assert r.status_code == 401


def test_approve_grants_the_role_and_stores_the_limits(client, admin_headers):
    user, profile = _demande()
    r = client.post(
        f"/api/admin/counselor-applications/{profile.id}/approve",
        json={"max_codes": 25, "max_uses_per_code": 1},
        headers=admin_headers,
    )
    assert r.status_code == 200
    db.session.refresh(user)
    db.session.refresh(profile)
    assert user.role == "counselor"
    assert profile.status == "approved"
    assert profile.max_codes == 25
    assert profile.max_uses_per_code == 1
    assert profile.reviewed_at is not None
    assert profile.reviewed_by_id is not None


def test_refresh_mints_the_counselor_claim_after_approval(client, admin_headers):
    """The guards no longer read the claim, but /auth/refresh still answers
    with the user from the row, so the context it feeds shows the new role."""
    user, profile = _demande()
    client.post(
        f"/api/admin/counselor-applications/{profile.id}/approve",
        json={}, headers=admin_headers,
    )
    refresh_headers = {
        "Authorization": "Bearer " + create_refresh_token(
            identity=str(user.id),
            additional_claims={"pwv": password_fingerprint(user.password_hash)},
        )
    }
    r = client.post("/api/auth/refresh", headers=refresh_headers)
    assert r.status_code == 200
    assert r.get_json()["user"]["role"] == "counselor"


def test_the_espace_opens_on_the_token_the_demande_was_signed_in_with(client, admin_headers):
    """The bug that sent new conseillers to log out and back in: their access
    token was minted while they were still a candidate, and the guards refused
    it for the rest of its hour. Approval must open the espace on the very next
    request, whatever claim the browser still carries."""
    user, profile = _demande()
    stale = {"Authorization": "Bearer " + create_access_token(
        identity=str(user.id), additional_claims={"role": "candidate"},
    )}
    assert client.get("/api/counselor/stats", headers=stale).status_code == 403

    client.post(
        f"/api/admin/counselor-applications/{profile.id}/approve",
        json={}, headers=admin_headers,
    )

    assert client.get("/api/counselor/stats", headers=stale).status_code == 200
    assert client.get("/api/counselor/codes", headers=stale).status_code == 200
    assert client.get("/api/counselor/beneficiaires", headers=stale).status_code == 200


def test_approve_with_no_limits_means_illimite(client, admin_headers):
    user, profile = _demande()
    r = client.post(
        f"/api/admin/counselor-applications/{profile.id}/approve",
        json={},
        headers=admin_headers,
    )
    assert r.status_code == 200
    db.session.refresh(profile)
    assert profile.max_codes is None
    assert profile.max_uses_per_code is None


def test_approve_refuses_a_negative_limit(client, admin_headers):
    _user, profile = _demande()
    r = client.post(
        f"/api/admin/counselor-applications/{profile.id}/approve",
        json={"max_codes": 0},
        headers=admin_headers,
    )
    assert r.status_code == 400


def test_reject_requires_a_reason_and_leaves_the_role_alone(client, admin_headers):
    user, profile = _demande()
    assert client.post(
        f"/api/admin/counselor-applications/{profile.id}/reject",
        json={}, headers=admin_headers,
    ).status_code == 400

    r = client.post(
        f"/api/admin/counselor-applications/{profile.id}/reject",
        json={"reason": "Structure non reconnue."},
        headers=admin_headers,
    )
    assert r.status_code == 200
    db.session.refresh(user)
    db.session.refresh(profile)
    assert profile.status == "rejected"
    assert profile.decision_reason == "Structure non reconnue."
    assert user.role == "candidate"


def test_revoke_takes_the_role_back_and_is_not_a_rejection(client, admin_headers):
    user, profile = _demande(status="approved")
    user.role = "counselor"
    db.session.commit()

    r = client.post(
        f"/api/admin/counselor-applications/{profile.id}/revoke",
        json={"reason": "Fin de convention."},
        headers=admin_headers,
    )
    assert r.status_code == 200
    db.session.refresh(user)
    db.session.refresh(profile)
    assert profile.status == "revoked"        # not "rejected"
    assert user.role == "candidate"


def test_limits_can_be_adjusted_after_approval(client, admin_headers):
    _user, profile = _demande(status="approved")
    r = client.put(
        f"/api/admin/counselor-applications/{profile.id}/limits",
        json={"max_codes": 50, "max_uses_per_code": 12},
        headers=admin_headers,
    )
    assert r.status_code == 200
    db.session.refresh(profile)
    assert profile.max_codes == 50
    assert profile.max_uses_per_code == 12


def test_deciding_never_demotes_an_admin(client, admin_headers):
    """Second lock on the door apply() already refuses at: a demande sitting on
    an admin account must not cost that account its role. On a single-admin
    install that is a lockout with no UI recovery."""
    user, profile = _demande(email="second-admin@test.com")
    user.role = "admin"
    db.session.commit()

    r = client.post(
        f"/api/admin/counselor-applications/{profile.id}/reject",
        json={"reason": "Test."}, headers=admin_headers,
    )
    assert r.status_code == 200
    db.session.refresh(user)
    assert user.role == "admin"


def test_a_decided_demande_cannot_be_approved_twice(client, admin_headers):
    _user, profile = _demande(status="rejected")
    r = client.post(
        f"/api/admin/counselor-applications/{profile.id}/approve",
        json={}, headers=admin_headers,
    )
    assert r.status_code == 409


def test_approving_mails_the_conseiller(client, admin_headers, app):
    _user, profile = _demande()
    with patch("app.services.email_service.send") as mock_send:
        client.post(
            f"/api/admin/counselor-applications/{profile.id}/approve",
            json={}, headers=admin_headers,
        )
    assert mock_send.called
    assert mock_send.call_args[0][0] == "conseiller@test.com"


def test_a_mail_failure_does_not_undo_the_approval(client, admin_headers, app):
    """send() is fail-soft, but pin it: the decision has already committed."""
    user, profile = _demande()
    with patch("app.services.email_service.send", return_value=False):
        r = client.post(
            f"/api/admin/counselor-applications/{profile.id}/approve",
            json={}, headers=admin_headers,
        )
    assert r.status_code == 200
    db.session.refresh(user)
    assert user.role == "counselor"


def _active_conseiller():
    user, profile = _demande(status="approved")
    user.role = "counselor"
    db.session.commit()
    return user, profile


def test_revoking_mails_the_conseiller_the_reason(client, admin_headers, app):
    _user, profile = _active_conseiller()
    with patch("app.services.email_service.send") as mock_send:
        r = client.post(
            f"/api/admin/counselor-applications/{profile.id}/revoke",
            json={"reason": "Fin de convention."}, headers=admin_headers,
        )
    assert r.status_code == 200
    mock_send.assert_called_once()
    to, subject, _html, text = mock_send.call_args[0]
    assert to == "conseiller@test.com"
    assert subject == "Votre accès conseiller"
    assert "Fin de convention." in text


@pytest.mark.parametrize("status, body", [
    ("pending", {"reason": "Fin de convention."}),   # 409: not an active conseiller
    ("approved", {}),                                # 400: no reason given
])
def test_a_refused_revocation_mails_nobody(client, admin_headers, app, status, body):
    _user, profile = _demande(status=status)
    with patch("app.services.email_service.send") as mock_send:
        r = client.post(
            f"/api/admin/counselor-applications/{profile.id}/revoke",
            json=body, headers=admin_headers,
        )
    assert r.status_code in (400, 409)
    mock_send.assert_not_called()


def test_a_mail_failure_does_not_undo_the_revocation(client, admin_headers, app):
    # Review Focus 4: the decision has committed before the mail is tried.
    user, profile = _active_conseiller()
    app.config["RESEND_API_KEY"] = "re_test"
    with patch("app.services.email_service.resend.Emails.send",
               side_effect=RuntimeError("resend down")):
        r = client.post(
            f"/api/admin/counselor-applications/{profile.id}/revoke",
            json={"reason": "Fin de convention."}, headers=admin_headers,
        )
    assert r.status_code == 200
    db.session.refresh(profile)
    db.session.refresh(user)
    assert profile.status == "revoked"
    assert user.role == "candidate"

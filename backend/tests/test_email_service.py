"""The app's first transactional email. Fail-soft by contract.

An approval that already committed must not 500 because Resend is down, so
every path here returns a bool and none of them raises.
"""
from unittest.mock import patch

from app.extensions import db
from app.models.counselor_profile import CounselorProfile
from app.models.user import User
from app.services import email_service


def _profile(status="approved", reason=None):
    u = User(email="conseiller@capemploi.fr", password_hash="x", role="counselor")
    db.session.add(u)
    db.session.commit()
    p = CounselorProfile(
        user_id=u.id, structure="Cap Emploi 31", fonction="Conseillère",
        telephone="0561000000", status=status, decision_reason=reason,
    )
    db.session.add(p)
    db.session.commit()
    return p


def test_send_without_a_key_returns_false_and_does_not_raise(app):
    app.config["RESEND_API_KEY"] = None
    assert email_service.send("a@b.fr", "Sujet", "<p>x</p>") is False


def test_send_swallows_a_provider_failure(app):
    app.config["RESEND_API_KEY"] = "re_test"
    with patch("app.services.email_service.resend.Emails.send", side_effect=RuntimeError("boom")):
        assert email_service.send("a@b.fr", "Sujet", "<p>x</p>") is False


def test_send_returns_true_on_success(app):
    app.config["RESEND_API_KEY"] = "re_test"
    with patch("app.services.email_service.resend.Emails.send", return_value={"id": "1"}):
        assert email_service.send("a@b.fr", "Sujet", "<p>x</p>") is True


def test_the_approval_mail_goes_to_the_login_address(app):
    app.config["RESEND_API_KEY"] = "re_test"
    profile = _profile()
    with patch("app.services.email_service.resend.Emails.send") as mock_send:
        assert email_service.send_counselor_approved(profile) is True
    payload = mock_send.call_args[0][0]
    assert payload["to"] == ["conseiller@capemploi.fr"]
    assert "conseiller" in payload["subject"].lower()


def test_the_rejection_mail_carries_the_reason(app):
    app.config["RESEND_API_KEY"] = "re_test"
    profile = _profile(status="rejected", reason="Structure non reconnue.")
    with patch("app.services.email_service.resend.Emails.send") as mock_send:
        email_service.send_counselor_rejected(profile)
    assert "Structure non reconnue." in mock_send.call_args[0][0]["html"]

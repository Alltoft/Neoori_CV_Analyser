"""The two account mails and their one-a-minute pace (email verification
spec, decisions 11 and 17–20)."""
import logging
import re
from datetime import datetime, timedelta
from unittest.mock import patch

from app.extensions import db
from app.models.profile import CONSENT_VERSION, Profile
from app.services import auth_mail, email_service
from app.utils import auth_links

SEND = "app.services.email_service.resend.Emails.send"
TOKEN = re.compile(r"token=([A-Za-z0-9_.\-]+)")


def _sent(mock_send) -> dict:
    return mock_send.call_args[0][0]


def test_the_verification_mail_links_to_the_app_with_a_live_token(app, make_user):
    app.config["RESEND_API_KEY"] = "re_test"
    app.config["APP_URL"] = "https://neoori.tech"
    user = make_user(verified=False)
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        assert email_service.send_verification(user, "/analyse/nouveau") is True
    mail = _sent(mock_send)
    assert mail["to"] == [user.email]
    assert mail["subject"] == "Confirmez votre adresse email"
    assert "https://neoori.tech/verifier-email?token=" in mail["html"]
    payload = auth_links.load_verify_token(TOKEN.search(mail["text"]).group(1)).payload
    assert payload["uid"] == user.id
    assert payload["next"] == "/analyse/nouveau"


def test_the_greeting_uses_the_prenom_escaped(app, make_user):
    app.config["RESEND_API_KEY"] = "re_test"
    user = make_user(verified=False)
    db.session.add(Profile(
        user_id=user.id, prenom="<b>Marie</b>",
        consent_at=datetime.utcnow(), consent_version=CONSENT_VERSION,
    ))
    db.session.commit()
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        email_service.send_verification(user)
    html = _sent(mock_send)["html"]
    assert "Bonjour &lt;b&gt;Marie&lt;/b&gt;," in html
    assert "<b>Marie</b>" not in html


def test_without_a_key_the_mail_is_not_sent(app, make_user):
    app.debug = False   # FLASK_DEBUG in a developer's shell must not flip this
    assert email_service.send_verification(make_user(verified=False)) is False


def test_on_a_laptop_without_a_key_the_link_goes_to_the_log(app, make_user, caplog):
    app.debug = True
    user = make_user(verified=False)
    with caplog.at_level(logging.WARNING):
        assert email_service.send_verification(user) is True
    assert "/verifier-email?token=" in caplog.text


def test_the_reset_mail_carries_a_reset_token(app, make_user):
    app.config["RESEND_API_KEY"] = "re_test"
    user = make_user()
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        assert email_service.send_password_reset(user) is True
    mail = _sent(mock_send)
    assert mail["subject"] == "Réinitialiser votre mot de passe"
    assert "/reinitialiser-mot-de-passe?token=" in mail["html"]
    token = TOKEN.search(mail["text"]).group(1)
    assert auth_links.load_reset_token(token).payload["uid"] == user.id


def test_send_passes_a_text_part_when_given(app):
    app.config["RESEND_API_KEY"] = "re_test"
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        email_service.send("a@b.fr", "Sujet", "<p>x</p>", text="x")
    assert _sent(mock_send)["text"] == "x"


def test_a_verification_mail_leaves_and_stamps_the_clock(app, make_user):
    app.config["RESEND_API_KEY"] = "re_test"
    user = make_user(verified=False)
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        assert auth_mail.verification_if_due(user) is True
    assert mock_send.call_count == 1
    assert user.auth_mail_sent_at is not None


def test_a_second_request_within_a_minute_sends_nothing(app, make_user):
    app.config["RESEND_API_KEY"] = "re_test"
    user = make_user(verified=False)
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        auth_mail.verification_if_due(user)
        assert auth_mail.verification_if_due(user) is True   # a link is on its way
        auth_mail.reset_if_due(user)                         # one clock for both mails
    assert mock_send.call_count == 1


def test_after_a_minute_the_next_mail_leaves(app, make_user):
    app.config["RESEND_API_KEY"] = "re_test"
    user = make_user()
    user.auth_mail_sent_at = datetime.utcnow() - timedelta(seconds=61)
    db.session.commit()
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        auth_mail.reset_if_due(user)
    assert mock_send.call_count == 1


def test_a_failed_send_leaves_the_clock_alone(app, make_user):
    app.config["RESEND_API_KEY"] = "re_test"
    user = make_user(verified=False)
    with patch(SEND, side_effect=RuntimeError("down")):
        assert auth_mail.verification_if_due(user) is False
    assert user.auth_mail_sent_at is None

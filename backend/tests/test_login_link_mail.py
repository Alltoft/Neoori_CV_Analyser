"""The email sign-in link: its mail and its one-a-minute pace (social
sign-in spec, decisions 4, 14 and 15)."""
import logging
import re
from datetime import datetime, timedelta
from unittest.mock import patch

from app.extensions import db
from app.models.login_link import LoginLink
from app.services import auth_mail, email_service
from app.utils import auth_links

SEND = "app.services.email_service.resend.Emails.send"
TOKEN = re.compile(r"token=([A-Za-z0-9_.\-]+)")


def _sent(mock_send) -> dict:
    return mock_send.call_args[0][0]


def _link_mail(app, email="marie@test.fr", user=None, next_path=None):
    app.config["RESEND_API_KEY"] = "re_test"
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        sent = auth_mail.login_link_if_due(email, user, next_path)
    return sent, mock_send


# ── the mail ──────────────────────────────────────────────────────────────────

def test_the_mail_links_to_the_landing_page(app):
    app.config["RESEND_API_KEY"] = "re_test"
    app.config["DOMAIN"] = "neoori.tech"
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        assert email_service.send_login_link("marie@test.fr", "", "tok.en") is True
    mail = _sent(mock_send)
    assert mail["to"] == ["marie@test.fr"]
    assert mail["subject"] == "Votre lien de connexion"
    assert "https://cv.neoori.tech/connexion/lien?token=tok.en" in mail["html"]
    assert "valable 15 minutes" in mail["text"] and "ne sert qu'une fois" in mail["text"]
    assert mail["text"].startswith("Bonjour,")


def test_the_greeting_uses_the_prenom(app):
    app.config["RESEND_API_KEY"] = "re_test"
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        email_service.send_login_link("marie@test.fr", "Marie", "t")
    assert _sent(mock_send)["text"].startswith("Bonjour Marie,")


def test_on_a_laptop_without_a_key_the_link_goes_to_the_log(app, caplog):
    app.debug = True
    with caplog.at_level(logging.WARNING):
        assert email_service.send_login_link("marie@test.fr", "", "t") is True
    assert "/connexion/lien?token=t" in caplog.text


# ── the pace ──────────────────────────────────────────────────────────────────

def test_a_link_reaches_an_address_with_no_account(app):
    sent, mock_send = _link_mail(app, next_path="/analyse/nouveau")
    assert sent is True and mock_send.call_count == 1
    payload = auth_links.load_login_token(TOKEN.search(_sent(mock_send)["text"]).group(1)).payload
    assert payload["email"] == "marie@test.fr" and payload["next"] == "/analyse/nouveau"
    # The test and the code share one session: a new one sees only what was committed.
    db.session.remove()
    row = db.session.get(LoginLink, payload["jti"])
    assert row.email_hash == auth_links.email_hash("marie@test.fr") and row.used_at is None


def test_an_address_without_an_account_gets_one_link_a_minute(app):
    _link_mail(app)
    sent, again = _link_mail(app)
    assert sent is True               # on its way: one left under a minute ago
    assert again.call_count == 0
    assert LoginLink.query.count() == 1


def test_after_a_minute_it_gets_another(app):
    _link_mail(app)
    LoginLink.query.update({"created_at": datetime.utcnow() - timedelta(seconds=61)})
    db.session.commit()
    _, again = _link_mail(app)
    assert again.call_count == 1
    assert LoginLink.query.count() == 2


def test_an_account_shares_the_clock_of_its_other_mails(app, make_user):
    user = make_user()
    user.auth_mail_sent_at = datetime.utcnow()     # a reset mail just left
    db.session.commit()
    sent, mock_send = _link_mail(app, email=user.email, user=user)
    assert sent is True and mock_send.call_count == 0


def test_a_link_to_an_account_stamps_its_clock(app, make_user):
    user = make_user()
    _link_mail(app, email=user.email, user=user)
    assert user.auth_mail_sent_at is not None


def test_a_failed_send_writes_nothing_and_blocks_no_retry(app):
    app.config["RESEND_API_KEY"] = "re_test"
    with patch(SEND, side_effect=RuntimeError("provider down")):
        assert auth_mail.login_link_if_due("marie@test.fr", None) is False
    assert LoginLink.query.count() == 0
    _, retry = _link_mail(app)
    assert retry.call_count == 1


def test_a_failed_send_to_an_account_leaves_its_clock_alone(app, make_user):
    user = make_user()
    app.config["RESEND_API_KEY"] = "re_test"
    with patch(SEND, side_effect=RuntimeError("provider down")):
        auth_mail.login_link_if_due(user.email, user)
    assert user.auth_mail_sent_at is None


def test_rows_older_than_a_day_are_purged(app):
    db.session.add(LoginLink(id="old", email_hash="0" * 64,
                             created_at=datetime.utcnow() - timedelta(hours=25)))
    db.session.commit()
    _link_mail(app)
    assert db.session.get(LoginLink, "old") is None

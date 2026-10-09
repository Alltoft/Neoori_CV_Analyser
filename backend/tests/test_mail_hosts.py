"""Where each mail links (subdomain split spec, decision 31): an account mail
to the host it was asked from, every other mail to cv, and never to a name
the request made up."""
from contextlib import nullcontext
from unittest.mock import patch

import pytest

from app.extensions import db
from app.models.counselor_profile import CounselorProfile
from app.services import email_service

SEND = "app.services.email_service.resend.Emails.send"


@pytest.fixture
def mailer(app):
    app.config.update(RESEND_API_KEY="re_test", DOMAIN="neoori.tech")
    return app


def _sent(mock_send) -> dict:
    return mock_send.call_args[0][0]


ACCOUNT_MAILS = {
    "verification": (lambda user: email_service.send_verification(user), "/verifier-email?token="),
    "reset": (lambda user: email_service.send_password_reset(user), "/reinitialiser-mot-de-passe?token="),
    "sign-in link": (lambda user: email_service.send_login_link(user.email, "", "tok"), "/connexion/lien?token=tok"),
    "password changed": (lambda user: email_service.send_password_changed(user), "/mot-de-passe-oublie"),
}


@pytest.mark.parametrize("mail", ACCOUNT_MAILS)
@pytest.mark.parametrize("host, origin", [
    ("cv.neoori.tech", "https://cv.neoori.tech"),
    ("voyage.neoori.tech", "https://voyage.neoori.tech"),
    ("neoori.tech", "https://cv.neoori.tech"),
    ("attacker.example", "https://cv.neoori.tech"),
])
def test_an_account_mail_links_to_the_host_it_was_asked_from(mailer, make_user, mail, host, origin):
    send, path = ACCOUNT_MAILS[mail]
    user = make_user(verified=False)
    with mailer.test_request_context("/api/auth/x", base_url=f"https://{host}"), \
            patch(SEND, return_value={"id": "1"}) as mock_send:
        assert send(user) is True
    sent = _sent(mock_send)
    assert f'href="{origin}{path}' in sent["html"]
    assert f"{origin}{path}" in sent["text"]
    # Review Focus 4: a forged Host never reaches a mail body.
    assert "attacker.example" not in sent["html"] + sent["text"]


@pytest.mark.parametrize("host, origin", [
    ("voyage.neoori.tech", "https://voyage.neoori.tech"),
    ("attacker.example", "https://cv.neoori.tech"),
])
def test_a_reset_asked_through_the_route_links_to_its_host(mailer, client, make_user, host, origin):
    make_user(email="marie@test.fr")
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        res = client.post("/api/auth/forgot-password", json={"email": "marie@test.fr"},
                          base_url=f"https://{host}")
    assert res.status_code == 200
    html = _sent(mock_send)["html"]
    assert f'href="{origin}/reinitialiser-mot-de-passe?token=' in html
    assert "attacker.example" not in html


CV_MAILS = {
    "analysis ready": (
        lambda: email_service.send_analysis_ready("m@test.fr", "", unlocked=False),
        "https://cv.neoori.tech/espace",
    ),
    "analysis failed": (
        lambda: email_service.send_analysis_failed("m@test.fr", "", unlocked=False, analysis_id="a-1"),
        "https://cv.neoori.tech/espace",
    ),
    "counselor analysis ready": (
        lambda: email_service.send_counselor_analysis_ready("c@test.fr"),
        "https://cv.neoori.tech/conseiller",
    ),
    "counselor analysis failed": (
        lambda: email_service.send_counselor_analysis_failed("c@test.fr"),
        "https://cv.neoori.tech/conseiller",
    ),
    "new demande": (
        lambda: email_service.send_new_demande("a@test.fr", ""),
        "https://cv.neoori.tech/admin/conseillers",
    ),
}


@pytest.mark.parametrize("mail", CV_MAILS)
@pytest.mark.parametrize("host", [None, "voyage.neoori.tech"])
def test_every_other_mail_links_to_cv(mailer, mail, host):
    send, link = CV_MAILS[mail]
    context = mailer.test_request_context("/", base_url=f"https://{host}") if host else nullcontext()
    with context, patch(SEND, return_value={"id": "1"}) as mock_send:
        assert send() is True
    assert f'href="{link}"' in _sent(mock_send)["html"]


def test_the_approval_mail_links_to_cv_even_when_approved_from_voyage(mailer, make_user):
    user = make_user(email="claire@capemploi.fr")
    profile = CounselorProfile(user_id=user.id, structure="Cap Emploi 31",
                               fonction="Conseillère", telephone="0561000000", status="approved")
    db.session.add(profile)
    db.session.commit()
    with mailer.test_request_context("/", base_url="https://voyage.neoori.tech"), \
            patch(SEND, return_value={"id": "1"}) as mock_send:
        assert email_service.send_counselor_approved(profile) is True
    assert 'href="https://cv.neoori.tech/conseiller"' in _sent(mock_send)["html"]

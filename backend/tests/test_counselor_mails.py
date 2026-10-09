"""Advisor-door runs mail their counselor, with no name and no content
(four-doors spec, decision 28)."""
from unittest.mock import patch

from app.extensions import db
from app.models.analysis import Analysis
from app.services import anthropic_service as svc
from app.services import email_service
from tests.helpers_doors import counselor, user

READY = "app.services.email_service.send_counselor_analysis_ready"
FAILED = "app.services.email_service.send_counselor_analysis_failed"
OWNER_READY = "app.services.email_service.send_analysis_ready"
SEND = "app.services.email_service.resend.Emails.send"


def _row(**fields):
    row = Analysis(inputs={"_path": "1", "prenom": "Zoé", "nom": "Durand"}, **fields)
    db.session.add(row)
    db.session.commit()
    return row.id


def test_a_finished_advisor_run_mails_its_counselor_only(app):
    c = counselor()
    email = c.email          # read now: _notify_outcome removes the session
    analysis_id = _row(door="advisor", counselor_id=c.id, status="success")
    with patch(READY) as ready, patch(OWNER_READY) as owner_ready:
        svc._notify_outcome(analysis_id)
    ready.assert_called_once_with(email)
    owner_ready.assert_not_called()


def test_a_failed_advisor_run_says_so(app):
    c = counselor()
    email = c.email
    analysis_id = _row(door="advisor", counselor_id=c.id, status="error")
    with patch(FAILED) as failed:
        svc._notify_outcome(analysis_id)
    failed.assert_called_once_with(email)


def test_an_unverified_counselor_gets_nothing(app):
    c = user("nonverifie@test.fr", role="counselor", verified=False)
    analysis_id = _row(door="advisor", counselor_id=c.id, status="success")
    with patch(READY) as ready:
        svc._notify_outcome(analysis_id)
    ready.assert_not_called()


def test_a_no_login_run_mails_nobody(app):
    analysis_id = _row(door="anonymous", status="success")
    with patch(READY) as ready, patch(OWNER_READY) as owner_ready:
        svc._notify_outcome(analysis_id)
    ready.assert_not_called()
    owner_ready.assert_not_called()


def test_the_mail_names_nobody_and_links_to_the_counselor_space(app):
    app.config["RESEND_API_KEY"] = "re_test"
    with patch(SEND, return_value={"id": "1"}) as send:
        assert email_service.send_counselor_analysis_ready("c@test.fr") is True
    params = send.call_args[0][0]
    assert params["subject"] == "Une analyse est prête"
    assert "Zoé" not in params["html"] and "Durand" not in params["text"]
    assert "/conseiller" in params["text"]

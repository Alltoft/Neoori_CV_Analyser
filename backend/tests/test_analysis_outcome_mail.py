"""The analysis outcome mail (transactional mails spec, 2026-10-02).

Every finished run mails its owner — ready or failed, first run or the second
one an unlock starts — after the row is committed, without report text, and
never at the cost of the status it reports on.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.extensions import db
from app.models.analysis import Analysis
from app.models.profile import Profile
from app.models.prompt_version import PromptVersion
from app.services import anthropic_service as svc
from app.services.anthropic_service import _section_keys

READY = "app.services.email_service.send_analysis_ready"
FAILED = "app.services.email_service.send_analysis_failed"
SEND = "app.services.email_service.resend.Emails.send"

# Written into every section of the streamed report, so a test can prove it
# never reaches a mail.
MARKER = "MARQUEUR-DU-RAPPORT"


def _queued(user=None, *, unlock_method=None, prompt=True, tier="free") -> str:
    if prompt:
        db.session.add(PromptVersion(version_label="test", system_prompt_text="x",
                                     is_active=True, path="1"))
    analysis = Analysis(
        user_id=user.id if user is not None else None,
        inputs={"_path": "1", "_tier": tier, "cv_text": "c" * 300, "cible_visee": "t" * 60},
        status="queued",
        unlock_method=unlock_method,
    )
    db.session.add(analysis)
    db.session.commit()
    return analysis.id


def _streaming_client(tier="free"):
    """A client whose stream writes every section of the tier."""
    chunks = [f'"{k}": {{"title": "T", "body_markdown": "{MARKER}", "items": []}},'
              for k in _section_keys("1", tier)]
    stream = MagicMock()
    stream.__enter__.return_value = stream
    stream.text_stream = iter(["{"] + chunks)
    stream.get_final_message.return_value = MagicMock(
        usage=MagicMock(input_tokens=100, output_tokens=200))
    client = MagicMock()
    client.messages.stream.return_value = stream
    return client


def _failing_client(message: str):
    client = MagicMock()
    client.messages.stream.side_effect = RuntimeError(message)
    return client


def _run(app, analysis_id, client) -> None:
    with patch.object(svc, "_get_client", return_value=client):
        svc._run_analysis(analysis_id, app)


def _row(analysis_id) -> Analysis:
    # The run committed from its own app context; this one still holds the
    # objects it created.
    db.session.expire_all()
    return db.session.get(Analysis, analysis_id)


def test_a_finished_analysis_mails_its_owner(app, make_user):
    user = make_user(email="marie@test.fr")
    aid = _queued(user)
    with patch(READY) as ready, patch(FAILED) as failed:
        _run(app, aid, _streaming_client())
    assert _row(aid).status == "success"
    ready.assert_called_once_with("marie@test.fr", "", unlocked=False)
    failed.assert_not_called()


def test_the_run_an_unlock_starts_says_complete(app, make_user):
    user = make_user(email="marie@test.fr")
    aid = _queued(user, unlock_method="payment", tier="paid")
    with patch(READY) as ready:
        _run(app, aid, _streaming_client("paid"))
    ready.assert_called_once_with("marie@test.fr", "", unlocked=True)


@pytest.mark.parametrize("message, status", [
    ("boom", "error"),
    ("Request timed out.", "timeout"),
])
def test_a_failed_run_mails_the_failure(app, make_user, message, status):
    user = make_user(email="marie@test.fr")
    aid = _queued(user)
    with patch(READY) as ready, patch(FAILED) as failed:
        _run(app, aid, _failing_client(message))
    assert _row(aid).status == status
    failed.assert_called_once_with("marie@test.fr", "", unlocked=False, analysis_id=aid)
    ready.assert_not_called()


def test_no_active_prompt_mails_the_failure(app, make_user):
    user = make_user(email="marie@test.fr")
    aid = _queued(user, prompt=False)
    client = _streaming_client()
    with patch(FAILED) as failed:
        _run(app, aid, client)
    assert _row(aid).status == "error"
    client.messages.stream.assert_not_called()
    failed.assert_called_once_with("marie@test.fr", "", unlocked=False, analysis_id=aid)


def test_an_unlocked_run_with_no_active_prompt_asks_for_a_reply(app, make_user):
    # Review Focus 2: the early exit strands an unlocked row just the same.
    app.config["RESEND_API_KEY"] = "re_test"
    user = make_user(email="marie@test.fr")
    aid = _queued(user, unlock_method="code", prompt=False)
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        _run(app, aid, _streaming_client())
    mail = mock_send.call_args[0][0]
    assert mail["subject"] == "Le déblocage de votre analyse n'a pas abouti"
    assert f"Référence : {aid}" in mail["text"]


def test_an_ownerless_analysis_mails_nobody(app):
    aid = _queued(None)
    with patch(READY) as ready:
        _run(app, aid, _streaming_client())
    assert _row(aid).status == "success"
    ready.assert_not_called()


def test_an_unproven_address_gets_nothing(app, make_user):
    aid = _queued(make_user(verified=False))
    with patch(READY) as ready:
        _run(app, aid, _streaming_client())
    ready.assert_not_called()


def test_the_mail_carries_the_prenom_and_no_report_text(app, make_user):
    app.config["RESEND_API_KEY"] = "re_test"
    user = make_user(email="marie@test.fr")
    db.session.add(Profile(user_id=user.id, prenom="Marie"))
    db.session.commit()
    aid = _queued(user)
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        _run(app, aid, _streaming_client())
    mail = mock_send.call_args[0][0]
    assert mail["text"].startswith("Bonjour Marie,\n\n")
    assert MARKER not in mail["html"]
    assert MARKER not in mail["text"]
    # The report did carry it: absent from the mail by design, not by accident.
    assert MARKER in _row(aid).raw_output


def test_a_mail_that_raises_leaves_the_status_alone(app, make_user):
    aid = _queued(make_user())
    with patch(READY, side_effect=RuntimeError("resend down")):
        _run(app, aid, _streaming_client())      # must not raise
    assert _row(aid).status == "success"


def test_the_mail_leaves_after_the_connection_is_released(app, make_user):
    """No pooled connection held across the HTTP call to Resend — the same
    discipline as the stream in _run_analysis."""
    aid = _queued(make_user())
    seen = []
    with patch(READY, side_effect=lambda *a, **k: seen.append(db.session().in_transaction())):
        _run(app, aid, _streaming_client())
    assert seen == [False]

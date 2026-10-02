"""Mails transactionnels, lot 2 (spec 2026-10-02): the renderer every mail
shares, and the builders that use it."""
from datetime import datetime
from unittest.mock import patch

from app.extensions import db
from app.models.counselor_profile import CounselorProfile
from app.models.profile import Profile
from app.models.user import User
from app.services import email_service
from app.services.email_service import FOOTER, _greeting, _mail, _Quote, prenom_of

SEND = "app.services.email_service.resend.Emails.send"

BUTTON_HTML = (
    '<p style="margin:24px 0"><a href="https://x.fr/v?token=abc" style="background:#c96442;'
    "color:#ffffff;padding:12px 20px;border-radius:8px;text-decoration:none;"
    'display:inline-block">Confirmer</a></p>'
)


def _sent(mock_send) -> dict:
    return mock_send.call_args[0][0]


# ── the renderer ─────────────────────────────────────────────────────────────

def test_the_account_mails_render_byte_for_byte_as_before():
    """Captured from _link_mail on 2026-10-02, before it became _mail: the
    verification and reset mails must not move by a character."""
    body, text = _mail(
        ["Bonjour Marie,", "Ligne <2> & fin."],
        button=("Confirmer", "https://x.fr/v?token=abc"),
        small="Petit texte.",
    )
    assert body == (
        "<p>Bonjour Marie,</p><p>Ligne &lt;2&gt; &amp; fin.</p>"
        + BUTTON_HTML
        + '<p style="font-size:13px">Petit texte.</p>'
    )
    assert text == (
        "Bonjour Marie,\n\nLigne <2> & fin.\n\nhttps://x.fr/v?token=abc\n\n"
        "Petit texte.\n\nneoori — pour nous écrire, répondez à ce message.\n"
    )


def test_a_mail_without_button_or_small_print_ends_on_the_footer():
    body, text = _mail(["Un.", "Deux."])
    assert body == "<p>Un.</p><p>Deux.</p>"
    assert text == f"Un.\n\nDeux.\n\n{FOOTER}\n"


def test_a_quote_sits_in_the_grey_box_escaped():
    body, text = _mail(["Avant.", _Quote('<b>x</b> & "y"'), "Après."])
    assert body == (
        "<p>Avant.</p>"
        '<p style="padding:12px;background:#f3eee2;border-radius:8px">'
        '&lt;b&gt;x&lt;/b&gt; &amp; "y"</p>'
        "<p>Après.</p>"
    )
    # The text form has no box: the words stand as their own paragraph.
    assert text == f'Avant.\n\n<b>x</b> & "y"\n\nAprès.\n\n{FOOTER}\n'


def test_the_greeting_has_no_name_slot_without_a_prenom():
    assert _greeting("Marie") == "Bonjour Marie,"
    assert _greeting("") == "Bonjour,"


def test_prenom_of_reads_the_profile_and_strips_it(app, make_user):
    user = make_user()
    assert prenom_of(user) == ""          # no profile row at all
    db.session.add(Profile(user_id=user.id, prenom="  Marie "))
    db.session.commit()
    assert prenom_of(user) == "Marie"


def test_a_blank_prenom_greets_without_a_name(app, make_user):
    # Review Focus 1: a prénom of spaces must not give « Bonjour    , ».
    app.config["RESEND_API_KEY"] = "re_test"
    user = make_user(verified=False)
    db.session.add(Profile(user_id=user.id, prenom="   "))
    db.session.commit()
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        email_service.send_verification(user)
    assert _sent(mock_send)["text"].startswith("Bonjour,\n\n")


# ── the five new mails ───────────────────────────────────────────────────────

def _revoked_profile(reason: str) -> CounselorProfile:
    user = User(email="conseiller@capemploi.fr", password_hash="x", role="candidate",
                email_verified_at=datetime.utcnow())
    db.session.add(user)
    db.session.commit()
    profile = CounselorProfile(
        user_id=user.id, structure="Cap Emploi 31", fonction="Conseillère",
        telephone="0561000000", status="revoked", decision_reason=reason,
    )
    db.session.add(profile)
    db.session.commit()
    return profile


def test_the_ready_mail_links_to_the_espace(app):
    app.config["RESEND_API_KEY"] = "re_test"
    app.config["APP_URL"] = "https://neoori.tech"
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        assert email_service.send_analysis_ready("marie@test.fr", "Marie", unlocked=False) is True
    mail = _sent(mock_send)
    assert mail["to"] == ["marie@test.fr"]
    assert mail["subject"] == "Votre analyse est prête"
    assert mail["text"].startswith(
        "Bonjour Marie,\n\nVotre analyse est prête. Elle est enregistrée dans votre espace.\n\n"
    )
    assert 'href="https://neoori.tech/espace"' in mail["html"]
    assert "Ouvrir mon espace" in mail["html"]
    assert "https://neoori.tech/espace" in mail["text"]


def test_the_ready_mail_after_an_unlock_says_complete(app):
    app.config["RESEND_API_KEY"] = "re_test"
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        email_service.send_analysis_ready("marie@test.fr", "", unlocked=True)
    mail = _sent(mock_send)
    assert mail["subject"] == "Votre analyse complète est prête"
    assert mail["text"].startswith(
        "Bonjour,\n\nLa version complète de votre analyse est prête. Elle remplace "
        "la version précédente dans votre espace.\n\n"
    )
    assert "/espace" in mail["html"]


def test_the_failure_mail_sends_the_candidate_back_to_the_espace(app):
    app.config["RESEND_API_KEY"] = "re_test"
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        email_service.send_analysis_failed("marie@test.fr", "Marie", unlocked=False, analysis_id="a-1")
    mail = _sent(mock_send)
    assert mail["subject"] == "Votre analyse n'a pas abouti"
    assert (
        "La génération de votre analyse n'a pas abouti. Vous pouvez relancer "
        "une analyse depuis votre espace."
    ) in mail["text"]
    assert "/espace" in mail["html"]
    assert "Référence" not in mail["text"]


def test_the_failure_mail_after_an_unlock_asks_for_a_reply(app):
    """The unlock dead end (a second unlock is a 409) stays in code: this mail
    is the way out, through the reply address, with the row id to find it by."""
    app.config["RESEND_API_KEY"] = "re_test"
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        email_service.send_analysis_failed("marie@test.fr", "Marie", unlocked=True, analysis_id="a-1")
    mail = _sent(mock_send)
    assert mail["subject"] == "Le déblocage de votre analyse n'a pas abouti"
    assert (
        "Votre déblocage est bien enregistré, mais la version complète n'a pas "
        "pu être générée. Répondez à ce message : nous la relançons pour vous."
    ) in mail["text"]
    assert "Référence : a-1" in mail["text"]
    assert "Référence : a-1" in mail["html"]
    assert "<a " not in mail["html"]      # no button: the espace offers nothing here


def test_the_demande_mail_greets_the_admin_and_links_to_the_queue(app):
    app.config["RESEND_API_KEY"] = "re_test"
    app.config["APP_URL"] = "https://neoori.tech"
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        assert email_service.send_new_demande("admin@neoori.tech", "Paul") is True
    mail = _sent(mock_send)
    assert mail["to"] == ["admin@neoori.tech"]
    assert mail["subject"] == "Nouvelle demande de compte conseiller"
    assert mail["text"].startswith(
        "Bonjour Paul,\n\nUne demande de compte conseiller attend votre décision.\n\n"
    )
    assert 'href="https://neoori.tech/admin/conseillers"' in mail["html"]


def test_the_revocation_mail_carries_the_reason_escaped(app):
    app.config["RESEND_API_KEY"] = "re_test"
    profile = _revoked_profile('<b>x</b> & "y"')
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        assert email_service.send_counselor_revoked(profile) is True
    mail = _sent(mock_send)
    assert mail["to"] == ["conseiller@capemploi.fr"]
    assert mail["subject"] == "Votre accès conseiller"
    assert "&lt;b&gt;x&lt;/b&gt; &amp;" in mail["html"]
    assert "<b>" not in mail["html"]
    assert mail["text"] == (
        "Bonjour,\n\nVotre accès conseiller a été retiré.\n\n"
        '<b>x</b> & "y"\n\n'
        "Les codes que vous avez déjà remis restent valables. Votre compte reste "
        "utilisable comme compte candidat.\n\n"
        "neoori — pour nous écrire, répondez à ce message.\n"
    )


def test_the_revocation_mail_fails_soft_on_a_post_commit_read(app):
    class _Lost:
        """A profile whose post-commit reload dies, as a dropped connection would."""
        id = "p-1"

        @property
        def user(self):
            raise RuntimeError("Lost connection to MySQL server during query")

    assert email_service.send_counselor_revoked(_Lost()) is False


def test_the_password_changed_mail_points_at_a_new_reset(app, make_user):
    app.config["RESEND_API_KEY"] = "re_test"
    app.config["APP_URL"] = "https://neoori.tech"
    user = make_user(email="marie@test.fr")
    db.session.add(Profile(user_id=user.id, prenom="Marie"))
    db.session.commit()
    with patch(SEND, return_value={"id": "1"}) as mock_send:
        assert email_service.send_password_changed(user) is True
    mail = _sent(mock_send)
    assert mail["to"] == ["marie@test.fr"]
    assert mail["subject"] == "Votre mot de passe a été modifié"
    assert mail["text"].startswith(
        "Bonjour Marie,\n\n"
        "Le mot de passe de votre compte neoori vient d'être modifié.\n\n"
        "Si c'est vous, il n'y a rien à faire.\n\n"
        "Si vous n'êtes pas à l'origine de ce changement, choisissez-en un nouveau "
        "tout de suite.\n\n"
    )
    assert 'href="https://neoori.tech/mot-de-passe-oublie"' in mail["html"]

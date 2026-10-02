"""Mails transactionnels, lot 2 (spec 2026-10-02): the renderer every mail
shares, and the builders that use it."""
from unittest.mock import patch

from app.extensions import db
from app.models.profile import Profile
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

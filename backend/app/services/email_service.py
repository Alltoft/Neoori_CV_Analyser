"""Transactional email. The app's first — resend was in requirements and
RESEND_API_KEY in config, with nothing calling either.

Fail-soft by contract: send() returns False and logs, and never raises. It is
called after the decision has already committed, and a provider outage must not
turn a successful approval into a 500 the admin retries.
"""
import html as html_escape

import resend
from flask import current_app

from ..models.counselor_profile import CounselorProfile
from ..models.profile import Profile
from ..utils import auth_links

FOOTER = "neoori — pour nous écrire, répondez à ce message."


def _app_url() -> str:
    return current_app.config["APP_URL"]


def send(to: str, subject: str, html: str, text: str | None = None) -> bool:
    key = current_app.config.get("RESEND_API_KEY")
    if not key:
        current_app.logger.warning("RESEND_API_KEY missing — mail to %s not sent.", to)
        return False
    try:
        resend.api_key = key
        params = {
            "from": current_app.config["MAIL_FROM"],
            "to": [to],
            "subject": subject,
            "html": html,
        }
        # A plain-text part: HTML-only mail scores worse with spam filters.
        if text is not None:
            params["text"] = text
        resend.Emails.send(params)
        return True
    except Exception:
        current_app.logger.exception("Mail to %s failed.", to)
        return False


def _layout(title: str, body: str) -> str:
    """One sober frame for every mail. Inline styles: mail clients drop <style>."""
    return (
        '<div style="font-family:Inter,Helvetica,Arial,sans-serif;color:#1d1a17;'
        'max-width:520px;margin:0 auto;padding:24px">'
        f'<h1 style="font-size:20px;margin:0 0 16px">{title}</h1>'
        f'{body}'
        '<p style="font-size:13px;color:rgba(29,26,23,0.55);margin-top:28px">'
        f'{FOOTER}</p>'
        '</div>'
    )


def send_counselor_approved(profile: CounselorProfile) -> bool:
    # profile was just committed at the call site, which expires the instance
    # (expire_on_commit=True) -- reading profile.user.email / max_codes below
    # is a real DB round-trip, not a free attribute access, so it can fail on
    # its own. Same fail-soft contract as send(): log and return False, never
    # raise, so a read failure here can't turn an already-committed approval
    # into a 500 the admin retries.
    try:
        limits = (
            f"<li>Nombre de codes : {profile.max_codes}</li>"
            if profile.max_codes is not None
            else "<li>Nombre de codes : illimité</li>"
        ) + (
            f"<li>Utilisations par code : {profile.max_uses_per_code}</li>"
            if profile.max_uses_per_code is not None
            else "<li>Utilisations par code : illimité</li>"
        )
        body = (
            "<p>Votre compte conseiller est activé.</p>"
            "<p>Vous pouvez maintenant créer des codes pour les personnes que vous "
            "accompagnez, et suivre leur utilisation depuis votre espace.</p>"
            f'<ul style="font-size:14px">{limits}</ul>'
            f'<p><a href="{_app_url()}/conseiller" '
            'style="color:#c96442">Ouvrir mon espace conseiller</a></p>'
        )
        return send(profile.user.email, "Votre compte conseiller est activé", _layout(
            "Compte conseiller activé", body,
        ))
    except Exception:
        # profile.id is itself an expired post-commit attribute, so reading it
        # here can trigger the very same kind of DB round-trip that just
        # failed above -- fall back rather than let the logging call raise.
        try:
            profile_id = profile.id
        except Exception:
            profile_id = "?"
        current_app.logger.exception(
            "Could not build/send the approval mail for profile %s.", profile_id
        )
        return False


def send_counselor_rejected(profile: CounselorProfile) -> bool:
    # Same reasoning as send_counselor_approved above: profile.user.email and
    # profile.decision_reason are post-commit reads that can themselves fail.
    try:
        reason = html_escape.escape(profile.decision_reason or "")
        body = (
            "<p>Votre demande de compte conseiller n'a pas été retenue.</p>"
            f'<p style="padding:12px;background:#f3eee2;border-radius:8px">{reason}</p>'
            "<p>Votre compte reste utilisable comme compte candidat.</p>"
        )
        return send(profile.user.email, "Votre demande de compte conseiller", _layout(
            "Demande non retenue", body,
        ))
    except Exception:
        # profile.id is itself an expired post-commit attribute, so reading it
        # here can trigger the very same kind of DB round-trip that just
        # failed above -- fall back rather than let the logging call raise.
        try:
            profile_id = profile.id
        except Exception:
            profile_id = "?"
        current_app.logger.exception(
            "Could not build/send the rejection mail for profile %s.", profile_id
        )
        return False


def _button(href: str, label: str) -> str:
    return (
        f'<p style="margin:24px 0"><a href="{href}" style="background:#c96442;'
        'color:#ffffff;padding:12px 20px;border-radius:8px;text-decoration:none;'
        f'display:inline-block">{label}</a></p>'
    )


class _Quote(str):
    """A paragraph _mail() sets in the grey box: someone else's words, such as
    an admin's reason. Escaped like every paragraph; plain in the text form."""


_QUOTE_STYLE = "padding:12px;background:#f3eee2;border-radius:8px"


def _mail(
    paragraphs: list[str],
    *,
    button: tuple[str, str] | None = None,
    small: str | None = None,
) -> tuple[str, str]:
    """The HTML body and the plain-text body of a mail, built from one copy so
    a wording edit cannot reach one form and miss the other. Paragraphs are
    plain text, escaped here for the HTML form only; a _Quote one goes in the
    grey box. `button` is (label, href): the text form prints the bare href."""
    def esc(s: str) -> str:
        return html_escape.escape(s, quote=False)

    body = "".join(
        f'<p style="{_QUOTE_STYLE}">{esc(p)}</p>' if isinstance(p, _Quote) else f"<p>{esc(p)}</p>"
        for p in paragraphs
    )
    parts = list(paragraphs)
    if button is not None:
        label, href = button
        body += _button(href, label)
        parts.append(href)
    if small is not None:
        body += f'<p style="font-size:13px">{esc(small)}</p>'
        parts.append(small)
    parts.append(FOOTER)
    return body, "\n\n".join(parts) + "\n"


def _greeting(prenom: str) -> str:
    return f"Bonjour {prenom}," if prenom else "Bonjour,"


def prenom_of(user) -> str:
    """The prénom on the person's profile, or "" when there is none. Public:
    the generation thread reads it before it releases its DB connection."""
    profile = Profile.query.filter_by(user_id=user.id).first()
    return (profile.prenom or "").strip() if profile else ""


def _deliver_link(to: str, subject: str, html: str, text: str, link: str) -> bool:
    """send(), except on a laptop with no key: the link goes to the log, so the
    local flow can be walked end to end. Debug only — never in production,
    where a token in a log line is a session for whoever reads the log."""
    if not current_app.config.get("RESEND_API_KEY") and current_app.debug:
        current_app.logger.warning("DEV — no RESEND_API_KEY, link for %s: %s", to, link)
        return True
    return send(to, subject, html, text)


def send_verification(user, next_path=None) -> bool:
    """« Confirmez votre adresse ». Fail-soft like every mail here."""
    try:
        link = f"{_app_url()}/verifier-email?token={auth_links.make_verify_token(user, next_path)}"
        body, text = _mail(
            [
                _greeting(prenom_of(user)),
                "Pour activer votre compte neoori, confirmez votre adresse : ouvrez le "
                "lien ci-dessous puis saisissez votre mot de passe. Il est valable 48 heures.",
            ],
            button=("Confirmer mon adresse", link),
            small="Si vous n'avez pas créé de compte, ignorez ce message.",
        )
        return _deliver_link(
            user.email, "Confirmez votre adresse email",
            _layout("Confirmez votre adresse", body), text, link,
        )
    except Exception:
        current_app.logger.exception("Could not build/send the verification mail.")
        return False


def send_password_reset(user) -> bool:
    """« Réinitialiser votre mot de passe ». Fail-soft."""
    try:
        link = f"{_app_url()}/reinitialiser-mot-de-passe?token={auth_links.make_reset_token(user)}"
        body, text = _mail(
            [
                "Une demande de réinitialisation a été faite pour votre compte. Le lien "
                "est valable 1 heure et ne sert qu'une fois.",
            ],
            button=("Choisir un nouveau mot de passe", link),
            small="Si vous n'êtes pas à l'origine de cette demande, ignorez ce message : "
            "votre mot de passe reste inchangé.",
        )
        return _deliver_link(
            user.email, "Réinitialiser votre mot de passe",
            _layout("Nouveau mot de passe", body), text, link,
        )
    except Exception:
        current_app.logger.exception("Could not build/send the reset mail.")
        return False


def send_login_link(to: str, prenom: str, token: str) -> bool:
    """« Votre lien de connexion ». One wording whatever the address's account
    state (social sign-in spec, decision 15): it goes to the inbox owner, and an
    address with no account gets the same link, which signs it up. Fail-soft."""
    try:
        link = f"{_app_url()}/connexion/lien?token={token}"
        body, text = _mail(
            [
                _greeting(prenom),
                "Voici votre lien pour accéder à neoori. Il est valable 15 minutes "
                "et ne sert qu'une fois.",
            ],
            button=("Accéder à neoori", link),
            small="Si vous n'avez pas demandé ce lien, ignorez ce message.",
        )
        return _deliver_link(
            to, "Votre lien de connexion",
            _layout("Votre lien de connexion", body), text, link,
        )
    except Exception:
        current_app.logger.exception("Could not build/send the sign-in link mail.")
        return False


# ── Lot 2 (transactional mails spec, 2026-10-02) ─────────────────────────────
# Each one leaves after the commit that decided it and says that something
# happened — never the content itself. Which of them link where, and which
# carry no link, is listed in CLAUDE.md (« Mails transactionnels »).


def send_analysis_ready(to: str, prenom: str, *, unlocked: bool) -> bool:
    """« Votre analyse est prête ». Plain values, not rows: the generation
    thread releases its DB connection before calling this. `unlocked` is the
    row's second run, started by a payment or a code (unlock_method set)."""
    try:
        if unlocked:
            subject, title = "Votre analyse complète est prête", "Analyse complète prête"
            line = (
                "La version complète de votre analyse est prête. Elle remplace la "
                "version précédente dans votre espace."
            )
        else:
            subject, title = "Votre analyse est prête", "Analyse prête"
            line = "Votre analyse est prête. Elle est enregistrée dans votre espace."
        body, text = _mail(
            [_greeting(prenom), line],
            button=("Ouvrir mon espace", f"{_app_url()}/espace"),
        )
        return send(to, subject, _layout(title, body), text)
    except Exception:
        current_app.logger.exception("Could not build/send the analysis-ready mail.")
        return False


def send_analysis_failed(to: str, prenom: str, *, unlocked: bool, analysis_id: str) -> bool:
    """« Votre analyse n'a pas abouti ». After an unlock the espace has nothing
    to offer — a second unlock is a 409 — so that variant asks for a reply and
    carries the row id to find it by. Relaunching it is the team's job."""
    try:
        if unlocked:
            subject, title = "Le déblocage de votre analyse n'a pas abouti", "Déblocage interrompu"
            body, text = _mail([
                _greeting(prenom),
                "Votre déblocage est bien enregistré, mais la version complète n'a pas pu "
                "être générée. Répondez à ce message : nous la relançons pour vous.",
                f"Référence : {analysis_id}",
            ])
        else:
            subject, title = "Votre analyse n'a pas abouti", "Analyse interrompue"
            body, text = _mail(
                [
                    _greeting(prenom),
                    "La génération de votre analyse n'a pas abouti. Vous pouvez relancer "
                    "une analyse depuis votre espace.",
                ],
                button=("Ouvrir mon espace", f"{_app_url()}/espace"),
            )
        return send(to, subject, _layout(title, body), text)
    except Exception:
        current_app.logger.exception(
            "Could not build/send the analysis-failed mail for %s.", analysis_id
        )
        return False


def send_new_demande(to: str, prenom: str) -> bool:
    """« Nouvelle demande de compte conseiller », to one address. Plain values:
    demande_mail picks the recipients. Nothing about the applicant: name,
    structure and phone stay behind the dashboard login."""
    try:
        body, text = _mail(
            [
                _greeting(prenom),
                "Une demande de compte conseiller attend votre décision.",
            ],
            button=("Voir les demandes", f"{_app_url()}/admin/conseillers"),
        )
        return send(
            to, "Nouvelle demande de compte conseiller",
            _layout("Nouvelle demande", body), text,
        )
    except Exception:
        current_app.logger.exception("Could not build/send the new-demande mail.")
        return False


def send_counselor_revoked(profile: CounselorProfile) -> bool:
    # Same reasoning as send_counselor_approved above: profile.user and
    # profile.decision_reason are post-commit reads that can themselves fail.
    # The reason is already shown on /conseiller; the mail discloses nothing new.
    try:
        user = profile.user
        body, text = _mail([
            _greeting(prenom_of(user)),
            "Votre accès conseiller a été retiré.",
            _Quote(profile.decision_reason or ""),
            "Les codes que vous avez déjà remis restent valables. Votre compte reste "
            "utilisable comme compte candidat.",
        ])
        return send(
            user.email, "Votre accès conseiller",
            _layout("Accès conseiller retiré", body), text,
        )
    except Exception:
        # profile.id is itself an expired post-commit attribute -- fall back
        # rather than let the logging call raise.
        try:
            profile_id = profile.id
        except Exception:
            profile_id = "?"
        current_app.logger.exception(
            "Could not build/send the revocation mail for profile %s.", profile_id
        )
        return False


def send_password_changed(user) -> bool:
    """« Votre mot de passe a été modifié », after a reset. Neither checks nor
    stamps auth_mail_sent_at: it follows a reset whose link that clock already
    paced, and it must reach the owner even when someone else held the link."""
    try:
        body, text = _mail(
            [
                _greeting(prenom_of(user)),
                "Le mot de passe de votre compte neoori vient d'être modifié.",
                "Si c'est vous, il n'y a rien à faire.",
                "Si vous n'êtes pas à l'origine de ce changement, choisissez-en un "
                "nouveau tout de suite.",
            ],
            button=("Choisir un nouveau mot de passe", f"{_app_url()}/mot-de-passe-oublie"),
        )
        return send(
            user.email, "Votre mot de passe a été modifié",
            _layout("Mot de passe modifié", body), text,
        )
    except Exception:
        current_app.logger.exception("Could not build/send the password-changed mail.")
        return False

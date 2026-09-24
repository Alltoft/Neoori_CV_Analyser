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

APP_URL = "https://neoori.tech"


def send(to: str, subject: str, html: str) -> bool:
    key = current_app.config.get("RESEND_API_KEY")
    if not key:
        current_app.logger.warning("RESEND_API_KEY missing — mail to %s not sent.", to)
        return False
    try:
        resend.api_key = key
        resend.Emails.send({
            "from": current_app.config["MAIL_FROM"],
            "to": [to],
            "subject": subject,
            "html": html,
        })
        return True
    except Exception:
        current_app.logger.exception("Mail to %s failed.", to)
        return False


def _layout(title: str, body: str) -> str:
    """One sober frame for both mails. Inline styles: mail clients drop <style>."""
    return (
        '<div style="font-family:Inter,Helvetica,Arial,sans-serif;color:#1d1a17;'
        'max-width:520px;margin:0 auto;padding:24px">'
        f'<h1 style="font-size:20px;margin:0 0 16px">{title}</h1>'
        f'{body}'
        '<p style="font-size:13px;color:rgba(29,26,23,0.55);margin-top:28px">'
        'neoori — ce message est automatique, il ne se répond pas.</p>'
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
            f'<p><a href="{APP_URL}/conseiller" '
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

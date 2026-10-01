"""When the two account mails may leave, and the clock that says so.

Shared by routes/auth.py and the conseiller demande, which creates accounts
too. One column, users.auth_mail_sent_at, paces both mails: an inbox gets at
most one account mail a minute whatever the endpoint, so neither
/resend-verification nor /forgot-password can be aimed at someone's address
to flood it (email verification spec, decision 11). The clock is stamped only
when a mail actually left, so a provider outage never blocks the retry.
"""
from datetime import datetime, timedelta

from ..extensions import db
from . import email_service

COOLDOWN = timedelta(seconds=60)


def cooldown_passed(user, now: datetime | None = None) -> bool:
    now = now or datetime.utcnow()
    return user.auth_mail_sent_at is None or now - user.auth_mail_sent_at >= COOLDOWN


def _stamp(user) -> None:
    user.auth_mail_sent_at = datetime.utcnow()
    db.session.commit()


def verification_if_due(user, next_path=None) -> bool:
    """True when a link is on its way: sent now, or sent under a minute ago."""
    if not cooldown_passed(user):
        return True
    if not email_service.send_verification(user, next_path):
        return False
    _stamp(user)
    return True


def reset_if_due(user) -> None:
    if cooldown_passed(user) and email_service.send_password_reset(user):
        _stamp(user)

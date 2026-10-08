"""When the account mails may leave, and the clocks that say so.

Shared by routes/auth.py and the conseiller demande, which creates accounts
too. One column, users.auth_mail_sent_at, paces both mails: an inbox gets at
most one account mail a minute whatever the endpoint, so neither
/resend-verification nor /forgot-password can be aimed at someone's address
to flood it (email verification spec, decision 11). The clock is stamped only
when a mail actually left, so a provider outage never blocks the retry.

The sign-in link (social sign-in spec, decision 14) also reaches addresses
with no account: those are paced by their latest login_links row instead.
"""
from datetime import datetime, timedelta
from uuid import uuid4

from ..extensions import db
from ..models.login_link import LoginLink
from ..utils import auth_links
from . import email_service

COOLDOWN = timedelta(seconds=60)
# A link lives 15 minutes and its pacing clock one: a day of rows is ample.
LINK_ROWS_KEPT = timedelta(hours=24)


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


def login_link_if_due(email: str, user, next_path=None) -> bool:
    """« Recevoir un lien de connexion ». True when a link is on its way: sent
    now, or sent under a minute ago.

    Paced per address whether or not it has an account: an account by the
    clock its other mails share, an address without one by its latest
    login_links row. Both are written only once Resend accepted the mail, so
    an outage never blocks the retry."""
    digest = auth_links.email_hash(email)
    now = datetime.utcnow()
    if not _link_cooldown_passed(digest, user, now):
        return True
    jti = str(uuid4())
    prenom = email_service.prenom_of(user) if user is not None else ""
    if not email_service.send_login_link(email, prenom, auth_links.make_login_token(jti, email, next_path)):
        return False
    LoginLink.query.filter(LoginLink.created_at < now - LINK_ROWS_KEPT).delete(
        synchronize_session=False
    )
    db.session.add(LoginLink(id=jti, email_hash=digest, created_at=now))
    if user is not None:
        user.auth_mail_sent_at = now
    db.session.commit()
    return True


def _link_cooldown_passed(digest: str, user, now: datetime) -> bool:
    if user is not None:
        return cooldown_passed(user, now)
    last = (
        LoginLink.query.filter_by(email_hash=digest)
        .order_by(LoginLink.created_at.desc())
        .first()
    )
    return last is None or now - last.created_at >= COOLDOWN

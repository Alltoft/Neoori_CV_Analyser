"""The admin's half of a conseiller demande: a mail when one joins the queue.

A demande becomes admin work when its address is proven —
admin.list_counselor_applications filters on email_verified_at (email
verification spec, decision 16). That happens at one of three doors, and each
calls notify_if_visible() after its own commit:

  counselor_space.apply()   a signed-in, hence verified, applicant
  auth.verify_email()       the email_verified_at None -> set write
  auth.reset_password()     the same write, made by a reset link

email_verified_at goes None -> set once per account, and an account holds one
demande, so each demande mails the admins once (transactional mails spec,
2026-10-02). Admin « Marquer comme vérifié » does not call this: the admin who
clicked is already looking at the queue.

Who is told: the addresses in ADMIN_NOTIFY_EMAIL (VPS .env) when it is set —
production sets it, because the shared admin login, admin@neoori.dev, has no
mailbox (neoori.dev has no MX record) and every copy sent there would bounce.
Unset, every verified admin, looked up at send time.
"""
from flask import current_app

from ..extensions import db
from ..models.counselor_profile import CounselorProfile
from ..models.user import User
from . import email_service


def _recipients() -> list[tuple[str, str]]:
    """(address, prénom) for everyone the demande mail goes to."""
    configured = current_app.config.get("ADMIN_NOTIFY_EMAILS") or []
    if configured:
        recipients = []
        for address in configured:
            # A named inbox needs no account; one that has an account is
            # greeted by its prénom like every other mail.
            account = User.query.filter_by(email=address).first()
            recipients.append((address, email_service.prenom_of(account) if account else ""))
        return recipients
    admins = User.query.filter(
        User.role == "admin", User.email_verified_at.isnot(None)
    ).all()
    return [(admin.email, email_service.prenom_of(admin)) for admin in admins]


def notify_if_visible(user) -> None:
    """Mail the admins that `user`'s demande is waiting. Fail-soft: the caller
    has committed, and a lookup or a provider failure must not turn a
    verification into a 500."""
    try:
        if user.email_verified_at is None:
            return
        if CounselorProfile.query.filter_by(user_id=user.id, status="pending").first() is None:
            return
        recipients = _recipients()
    except Exception:
        current_app.logger.exception("Could not look up the demande or the admins to tell.")
        # Every caller has already committed; a failed lookup may have left the
        # session pending rollback, so the request's next query must not 500.
        db.session.rollback()
        return
    if not recipients:
        current_app.logger.warning(
            "A conseiller demande is waiting, and no verified admin to tell "
            "(ADMIN_NOTIFY_EMAIL is unset)."
        )
        return
    # One send per address. send_new_demande is fail-soft, so one bad address
    # does not cost the others their mail.
    for address, prenom in recipients:
        email_service.send_new_demande(address, prenom)

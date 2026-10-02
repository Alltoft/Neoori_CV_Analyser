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
"""
from flask import current_app

from ..models.counselor_profile import CounselorProfile
from ..models.user import User
from . import email_service


def notify_if_visible(user) -> None:
    """Mail every verified admin that `user`'s demande is waiting. Fail-soft:
    the caller has committed, and an admin lookup or a provider failure must
    not turn a verification into a 500."""
    try:
        if user.email_verified_at is None:
            return
        if CounselorProfile.query.filter_by(user_id=user.id, status="pending").first() is None:
            return
        # Looked up at send time, so adding or removing an admin in /admin
        # moves the mail with it — no address to keep in the VPS env.
        admins = User.query.filter(
            User.role == "admin", User.email_verified_at.isnot(None)
        ).all()
    except Exception:
        current_app.logger.exception("Could not look up the demande or the admins to tell.")
        return
    if not admins:
        current_app.logger.warning("A conseiller demande is waiting, and no verified admin to tell.")
        return
    # One send per address. send_new_demande is fail-soft, so one bad address
    # does not cost the others their mail.
    for admin in admins:
        email_service.send_new_demande(admin)

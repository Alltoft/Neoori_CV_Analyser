"""The neoori_hold cookie (four-doors spec, decisions 34-36).

A signed-out draft has to survive a sign-in round trip — a Google redirect, or
the verification mail opened on a phone — without its key ever travelling in a
URL, a mail or a log. The key sits in this HttpOnly cookie; the row stores only
its hash. The same cookie carries a no-login report handed over by « Garder ».
One held row at a time: the last one held wins. A report displaced that way is
still reachable by its own link — « Garder » never clears its key.

Nothing here attaches a row to an account before the signup password has
proven its address (decision 36): signup only marks the row
(`pending_user_id`), verify-email attaches it, and any other proof of the
address drops the mark.

A held draft belongs to the browser, not to an account, so logout deletes it
(`drop_held_draft`): on a shared computer it must not be handed to the next
person who reads /held or signs in and claims.
"""
from datetime import datetime, timedelta

from flask import current_app, request

from ..extensions import db
from ..models.analysis import Analysis
from ..utils.tokens import hash_token, new_access_token

COOKIE = "neoori_hold"
TOO_MANY = "Le service est très demandé : connectez-vous d’abord, puis revenez à ce formulaire."
# Every /api route that reads it: drafts, claim, and /auth/register.
PATH = "/api"


def _secure() -> bool:
    return bool(current_app.config.get("SESSION_COOKIE_SECURE"))


def set_cookie(response, token: str) -> None:
    response.set_cookie(
        COOKIE, token,
        max_age=current_app.config["HELD_DRAFT_RETENTION_HOURS"] * 3600,
        path=PATH, httponly=True, samesite="Lax", secure=_secure(),
    )


def clear_cookie(response) -> None:
    response.delete_cookie(COOKIE, path=PATH, httponly=True, samesite="Lax", secure=_secure())


def held_row(*, draft_only: bool = False) -> Analysis | None:
    """The ownerless row this browser's cookie holds, or None."""
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    row = Analysis.query.filter_by(access_token_hash=hash_token(token)).first()
    if row is None or row.user_id is not None:
        return None
    if draft_only and row.status != "draft":
        return None
    return row


def too_many() -> bool:
    """The global ceiling on ownerless drafts alive at once (spec decision 40):
    nginx limits each address, this limits all of them together."""
    since = datetime.utcnow() - timedelta(hours=current_app.config["HELD_DRAFT_RETENTION_HOURS"])
    alive = Analysis.query.filter(
        Analysis.status == "draft",
        Analysis.user_id.is_(None),
        Analysis.access_token_hash.isnot(None),
        Analysis.created_at >= since,
    ).count()
    return alive >= current_app.config["HELD_DRAFTS_MAX"]


def new_held_draft(inputs: dict) -> tuple[Analysis, str]:
    """A new ownerless draft and the raw key for its cookie. Caller commits."""
    token = new_access_token()
    row = Analysis(inputs=inputs, status="draft", access_token_hash=hash_token(token))
    db.session.add(row)
    return row, token


def attach(row: Analysis, user_id: str) -> None:
    """The row becomes the account's own. Its key dies: an old link to it, or
    a stale cookie, now finds nothing. Caller commits."""
    row.user_id = user_id
    row.access_token_hash = None
    row.pending_user_id = None
    if row.status == "draft":
        # The account's newest draft from now on: the cross-device fallback
        # on the form picks the latest draft (spec decision 34).
        row.created_at = datetime.utcnow()


def mark_for(user_id: str) -> bool:
    """Password signup: the held row waits for this account. Caller commits."""
    row = held_row()
    if row is None:
        return False
    row.pending_user_id = user_id
    return True


def attach_pending(user_id: str) -> int:
    """verify-email, with the signup password: attach what signup marked."""
    rows = Analysis.query.filter_by(pending_user_id=user_id, user_id=None).all()
    for row in rows:
        attach(row, user_id)
    return len(rows)


def drop_held_draft() -> bool:
    """Logout: delete the draft this browser's cookie holds, so the next person
    on this computer finds nothing to read back or claim. A held no-login
    report stays: its own link still reaches it. Caller commits."""
    row = held_row(draft_only=True)
    if row is None:
        return False
    db.session.delete(row)
    return True


def unmark(user_id: str) -> int:
    """The address was proven without the signup password: whoever registered
    it may have been someone else, so nothing they held joins the account. The
    rows stay held by the browser that made them, and expire with it."""
    return Analysis.query.filter_by(pending_user_id=user_id).update(
        {"pending_user_id": None}, synchronize_session=False
    )

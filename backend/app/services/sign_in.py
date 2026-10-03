"""Who a Google, Microsoft or email-link sign-in is, and which account it
enters (social sign-in spec, decisions 1, 3, 7–9, 18 and 19).

Every new door ends in routes/auth._issue_session(), like the password one.
This module decides what comes before it:

  * whether a provider's address can be believed (trusted_email);
  * which existing account a sign-in enters, if any (existing_account),
    applying ruling 4 on the way in (enter);
  * or, for someone with no account yet, the signup ticket that carries them
    to « Finaliser votre inscription » — no users row exists before the CGV
    consent is given there.
"""
import secrets
from dataclasses import dataclass
from datetime import datetime

from flask import current_app, request

from ..extensions import bcrypt, db
from ..models.auth_identity import PROVIDERS, AuthIdentity
from ..models.profile import PRENOM_MAX_LENGTH
from ..models.user import User
from ..utils import auth_links
from . import demande_mail

# The tenant every personal Microsoft account (Outlook, Hotmail, Live) signs
# in under. Microsoft vouches for those addresses; in a work or school tenant
# only xms_edov does (decision 7).
MSA_TENANT_ID = "9188040d-6c67-4c5b-b112-36a304b66dad"

SIGNUP_COOKIE = "signup_ticket"
SIGNUP_COOKIE_PATH = "/api/auth"
TICKET_METHODS = PROVIDERS + ("email",)


@dataclass(frozen=True)
class Outcome:
    """Where a provider sign-in goes: "user" (an account, already entered),
    "signup" (a trusted address with no account) or "refused"."""
    kind: str
    user: User | None = None
    email: str | None = None


def unusable_password_hash() -> str:
    """A real bcrypt hash of a secret nobody holds (decision 3): every
    password typed against it fails like a wrong one, while pwv, the refresh
    check and the reset link work on it unchanged. token_urlsafe rather than
    raw bytes: bcrypt refuses a NUL byte."""
    return bcrypt.generate_password_hash(secrets.token_urlsafe(32)).decode("utf-8")


def trusted_email(provider: str, claims) -> str | None:
    """The address this ID token proves, in its stored form, or None."""
    email = auth_links.normalise_email(claims.get("email"))
    if not auth_links.email_shape_ok(email):
        return None
    if provider == "google":
        return email if claims.get("email_verified") is True else None
    if provider == "microsoft":
        if claims.get("tid") == MSA_TENANT_ID or _xms_edov(claims.get("xms_edov")):
            return email
    return None


def _xms_edov(value) -> bool:
    """Microsoft sends the flag as a boolean or, in some forms, a string."""
    return value is True or (isinstance(value, str) and value.strip().lower() in ("1", "true"))


def microsoft_issuer_ok(claims) -> bool:
    """`iss` names the token's own tenant (decision 6). The /common metadata
    publishes a template issuer, so Authlib's default check can never pass."""
    tid = claims.get("tid")
    return (
        isinstance(tid, str) and bool(tid)
        and claims.get("iss") == f"https://login.microsoftonline.com/{tid}/v2.0"
    )


def enter(user: User, provider: str | None = None, sub: str | None = None) -> None:
    """Let a proven sign-in into `user` (decision 9): link the provider
    identity if one is given, and apply ruling 4 to an account nobody had
    verified — the password a stranger may have set is replaced, the address
    counts as proven, and a demande waiting on that proof joins the queue."""
    if provider and not AuthIdentity.query.filter_by(provider=provider, subject=sub).first():
        db.session.add(AuthIdentity(user_id=user.id, provider=provider, subject=sub))
    newly_verified = user.email_verified_at is None
    if newly_verified:
        user.password_hash = unusable_password_hash()
        user.email_verified_at = datetime.utcnow()
    db.session.commit()
    if newly_verified:
        demande_mail.notify_if_visible(user)


def _account_at(email: str) -> User | None:
    """The account the database files under this address. On MySQL the
    users.email collation (utf8mb4_unicode_ci) ignores accents and invisible
    characters, so the row found may hold a different address that only
    collates equal: callers compare before trusting it."""
    return User.query.filter_by(email=email).first()


def existing_account(provider: str | None, sub: str | None, email: str | None) -> User | None:
    """The account this sign-in enters, already entered, or None (decision 8,
    branches 1 and 2). A known identity wins even when the provider's address
    changed; an address is matched only when the caller has proven it."""
    if provider and sub:
        identity = AuthIdentity.query.filter_by(provider=provider, subject=sub).first()
        if identity is not None:
            user = db.session.get(User, identity.user_id)
            enter(user)
            return user
    if email:
        user = _account_at(email)
        # Enter only the account OF the proven address. A row that merely
        # collates equal (« jean@société.fr » for « jean@societe.fr ») belongs
        # to someone else. Normalising the stored side keeps a legacy
        # mixed-case address enterable.
        if user is not None and auth_links.normalise_email(user.email) == email:
            enter(user, provider, sub)
            return user
    return None


def address_in_use(email: str) -> bool:
    """Whether the database already holds an account under this address,
    exactly or by collation. A sign-in that matched no account exactly must
    not create one here: the unique index would refuse it."""
    return _account_at(email) is not None


def resolve_oauth(provider: str, claims) -> Outcome:
    """Decision 8 in order: known identity, trusted address of an account,
    trusted address without one (signup), anything else refused — including a
    trusted address already held by a lookalike account, which is neither
    entered nor signed up."""
    email = trusted_email(provider, claims)
    user = existing_account(provider, claims["sub"], email)
    if user is not None:
        return Outcome("user", user=user)
    if email is None or address_in_use(email):
        return Outcome("refused")
    return Outcome("signup", email=email)


def set_signup_ticket(response, *, method: str, sub: str | None, email: str,
                      prenom_hint=None, next_path=None) -> None:
    """Carry someone with no account to « Finaliser votre inscription »
    (decision 18). A cookie, not a URL parameter: the provider subject and the
    address stay out of browser history and the nginx log. The hint is cut to
    what profiles.prenom holds, so the form it prefills can always be sent."""
    hint = prenom_hint.strip()[:PRENOM_MAX_LENGTH] if isinstance(prenom_hint, str) else ""
    try:
        # given_name is the provider's text, not ours: a lone surrogate in it
        # cannot be serialised into the ticket. A hint is only a convenience,
        # so it is dropped rather than failing the sign-in.
        hint.encode("utf-8")
    except UnicodeEncodeError:
        hint = ""
    token = auth_links.make_signup_ticket(
        method=method, sub=sub, email=email, prenom_hint=hint, next_path=next_path,
    )
    response.set_cookie(
        SIGNUP_COOKIE, token,
        max_age=auth_links.SIGNUP_MAX_AGE,
        path=SIGNUP_COOKIE_PATH,
        httponly=True,
        samesite="Lax",
        secure=current_app.config.get("SESSION_COOKIE_SECURE", False),
    )


def clear_signup_ticket(response) -> None:
    response.delete_cookie(
        SIGNUP_COOKIE,
        path=SIGNUP_COOKIE_PATH,
        httponly=True,
        samesite="Lax",
        secure=current_app.config.get("SESSION_COOKIE_SECURE", False),
    )


def live_signup_ticket() -> tuple[dict | None, str | None]:
    """(ticket, None) for this request's live, well-formed signup ticket;
    else (None, "link_expired" | "link_invalid")."""
    result = auth_links.load_signup_ticket(request.cookies.get(SIGNUP_COOKIE))
    if result.error:
        return None, result.error
    ticket = result.payload
    method, sub, email = ticket.get("method"), ticket.get("sub"), ticket.get("email")
    if method not in TICKET_METHODS or not (isinstance(email, str) and email):
        return None, "link_invalid"
    if method != "email" and not (isinstance(sub, str) and sub):
        return None, "link_invalid"
    return ticket, None

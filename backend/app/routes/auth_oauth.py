"""« Continuer avec Google / Microsoft »: the server-side authorization-code
flow (social sign-in spec, decisions 5–13).

No provider JavaScript runs on our pages: the button is a link to /start,
the provider sends the browser back to /callback, and every way out of
/callback is a redirect — into a session, to « Finaliser votre inscription »,
or to /connexion with an error code the page turns into a French sentence.
"""
import secrets

from flask import Blueprint, abort, current_app, jsonify, redirect, request, session

from ..extensions import db
from ..models.auth_identity import PROVIDERS
from ..services import oauth_clients, sign_in
from ..utils import auth_links
# The one place a session opens, and where a signed-in person lands.
from .auth import _issue_session, _landing

auth_oauth_bp = Blueprint("auth_oauth", __name__)

# Where /start keeps `next` for its callback, tied to the state it belongs
# to. One slot: of two sign-ins started in parallel, the earlier lands on its
# home rather than on a destination meant for the other.
_NEXT_SLOT = "oauth_next"


@auth_oauth_bp.get("/providers")
def providers():
    """Which buttons the sign-in pages show (decision 13)."""
    return jsonify(oauth_clients.configured()), 200


@auth_oauth_bp.get("/<provider>/start")
def start(provider):
    if provider not in PROVIDERS:
        abort(404)
    client = oauth_clients.client(provider)
    if client is None:
        return _to_connexion("indisponible")
    state = secrets.token_urlsafe(32)
    session[_NEXT_SLOT] = {"state": state, "next": auth_links.safe_next(request.args.get("next"))}
    # Authlib keeps one entry per /start (the authorize URL, PKCE verifier and
    # nonce) and sweeps only expired ones at a callback: on a shared computer,
    # abandoned starts would grow the session cookie past the browser's 4 KB
    # limit, after which every provider sign-in in that browser fails. One
    # live sign-in per provider per browser, like the single `next` slot.
    for key in [k for k in session if k.startswith(f"_state_{provider}_")]:
        session.pop(key, None)
    try:
        return client.authorize_redirect(
            _redirect_uri(provider), state=state, **oauth_clients.AUTHORIZE_PARAMS[provider]
        )
    except Exception:
        # Most often the provider's discovery document is unreachable.
        current_app.logger.exception("OAuth start failed for %s.", provider)
        session.pop(_NEXT_SLOT, None)
        return _to_connexion("echec")


@auth_oauth_bp.get("/<provider>/callback")
def callback(provider):
    if provider not in PROVIDERS:
        abort(404)
    client = oauth_clients.client(provider)
    if client is None:
        return _to_connexion("indisponible")

    slot = session.pop(_NEXT_SLOT, None) or {}
    next_path = (
        auth_links.safe_next(slot.get("next"))
        if slot.get("state") == request.args.get("state") else None
    )

    error = request.args.get("error")
    if error:
        if error != "access_denied":
            # Setup and policy failures (unauthorized_client, invalid_request,
            # a tenant's consent policy) are what to expect when the keys
            # first go live, and the redirect hides which. Both values are the
            # provider's, or an attacker's forging this URL: capped, and %r
            # keeps them on one log line.
            current_app.logger.warning(
                "OAuth provider error for %s: %r %r", provider, error[:100],
                (request.args.get("error_description") or "")[:300],
            )
        # The flow ends here: its state goes, as a completed flow's does.
        client.framework.clear_state_data(session, request.args.get("state"))
        return _to_connexion("annule" if error == "access_denied" else "echec")

    try:
        token = client.authorize_access_token(
            claims_options=oauth_clients.claims_options(provider, client.client_id)
        )
        claims = token.get("userinfo") or {}
        sub = claims.get("sub")
        # OIDC Core: sub is ASCII, at most 255 characters — auth_identities.subject
        # holds 255, which SQLite tests never enforce. Screened before
        # resolve_oauth, which commits identity links.
        if not isinstance(sub, str) or not sub or not sub.isascii() or len(sub) > 255:
            raise ValueError("the provider sent no usable ID token subject")
        outcome = sign_in.resolve_oauth(provider, claims)
    except Exception:
        # A dead or replayed state, a refused token, the provider or the
        # database failing: the person is on a browser navigation, and a
        # 500 page there is a dead end.
        db.session.rollback()
        current_app.logger.exception("OAuth callback failed for %s.", provider)
        return _to_connexion("echec")

    if outcome.kind == "refused":
        return _to_connexion("email_non_verifie")
    if outcome.kind == "signup":
        response = redirect("/inscription/finaliser")
        sign_in.set_signup_ticket(
            response, method=provider, sub=claims["sub"], email=outcome.email,
            prenom_hint=claims.get("given_name"), next_path=next_path,
        )
        return response
    response = redirect(_landing(outcome.user, {"next": next_path}) or _home_path(outcome.user.role))
    _issue_session(response, outcome.user)
    return response


def _redirect_uri(provider: str) -> str:
    """From APP_URL, never the request: behind nginx, Flask sees backend:5000."""
    return f"{current_app.config['APP_URL']}/api/auth/{provider}/callback"


def _to_connexion(code: str):
    return redirect(f"/connexion?erreur={code}")


def _home_path(role: str) -> str:
    """The role's home. frontend/src/lib/home.ts homeFor says the same:
    keep the two in step."""
    if role == "admin":
        return "/admin"
    if role == "counselor":
        return "/conseiller"
    return "/espace"

"""« Continuer avec Google / Microsoft »: the server-side authorization-code
flow (social sign-in spec, decisions 5–13).

No provider JavaScript runs on our pages: the button is a link to /start,
the provider sends the browser back to /callback, and every way out of
/callback is a redirect — into a session, to « Finaliser votre inscription »,
or to /connexion with an error code the page turns into a French sentence.
"""
import secrets
from urllib.parse import quote

from flask import Blueprint, abort, current_app, jsonify, redirect, request, session

from ..extensions import db
from ..models.auth_identity import PROVIDERS
from ..services import oauth_clients, sign_in
from ..utils import auth_links, site
# The one place a session opens, and where a signed-in person lands.
from .auth import _issue_session, _landing

auth_oauth_bp = Blueprint("auth_oauth", __name__)

# Where /start keeps `next` for its callback, tied to the state it belongs
# to. One slot, like the one live state per provider that start keeps: a
# later /start with the same provider replaces both, so an earlier tab's
# callback fails cleanly with « echec ». A later one with the other provider
# leaves the earlier state alone, and that sign-in lands on its home rather
# than on a destination meant for the other.
_NEXT_SLOT = "oauth_next"


@auth_oauth_bp.get("/providers")
def providers():
    """Which buttons the sign-in pages show (decision 13)."""
    return jsonify(oauth_clients.configured()), 200


@auth_oauth_bp.get("/<provider>/start")
def start(provider):
    if provider not in PROVIDERS:
        abort(404)
    # A sign-in ends on the host it started on: the callback is registered for
    # cv and voyage, and the state cookie stays on one host (subdomain split
    # spec, decision 28). Anywhere else — the root has no sign-in page — goes
    # to cv's /start, `next` kept, before any state is written.
    if site.request_app() not in ("cv", "voyage"):
        target = f"{site.origin('cv')}/api/auth/{provider}/start"
        if request.args.get("next") is not None:
            target += "?next=" + quote(request.args["next"], safe="")
        return redirect(target)
    client = oauth_clients.client(provider)
    next_path = auth_links.safe_next(request.args.get("next"))
    if client is None:
        return _to_connexion("indisponible", next_path)
    state = secrets.token_urlsafe(32)
    session[_NEXT_SLOT] = {"state": state, "next": next_path}
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
        return _to_connexion("echec", next_path)


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
        return _to_connexion("annule" if error == "access_denied" else "echec", next_path)

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
        # Choosing the landing queries the database too (a conseiller's
        # demande): inside the try, so a failure there redirects as well.
        landing = None
        if outcome.kind == "user":
            landing = (
                _landing(outcome.user, {"next": next_path})
                or _home_path(outcome.user.role, site.request_app())
            )
    except Exception:
        # A dead or replayed state, a refused token, the provider or the
        # database failing: the person is on a browser navigation, and a
        # 500 page there is a dead end.
        db.session.rollback()
        current_app.logger.exception("OAuth callback failed for %s.", provider)
        return _to_connexion("echec", next_path)

    if outcome.kind == "refused":
        return _to_connexion("email_non_verifie", next_path)
    if outcome.kind == "signup":
        response = redirect("/inscription/finaliser")
        sign_in.set_signup_ticket(
            response, method=provider, sub=claims["sub"], email=outcome.email,
            prenom_hint=claims.get("given_name"), next_path=next_path,
        )
        return response
    response = redirect(landing)
    _issue_session(response, outcome.user)
    return response


def _redirect_uri(provider: str) -> str:
    """On the host the sign-in started on, rebuilt from DOMAIN — never the
    Host header itself (subdomain split spec, decision 28). Both callbacks
    are registered with each provider."""
    return f"{site.request_origin()}/api/auth/{provider}/callback"


def _to_connexion(code: str, next_path: str | None = None):
    """/connexion with the error code its page turns into a sentence, and the
    destination the sign-in was heading for: the page reads `redirect`
    through safeRedirect, so the retry keeps it."""
    url = f"/connexion?erreur={code}"
    if next_path:
        url += "&redirect=" + quote(next_path, safe="")
    return redirect(url)


def _home_path(role: str, app: str | None = None) -> str:
    """The role's home on this host: a candidate's is the voyage hub on
    voyage and /espace anywhere else; a counselor's and an admin's are the
    same everywhere (subdomain split spec, decision 15).
    frontend/src/lib/home.ts homeFor says the same: keep the two in step."""
    if role == "admin":
        return "/admin"
    if role == "counselor":
        return "/conseiller"
    return "/voyage" if app == "voyage" else "/espace"

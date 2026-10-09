"""Google and Microsoft as OpenID Connect providers (social sign-in spec,
decisions 5, 6, 13 and 25).

A client exists only once both its keys are in the config: until then the
provider is "not configured", its button stays hidden and /start answers
« indisponible ». Clients are registered on first use, in a registry that
belongs to the app: the factory — and the test suite — build many apps, and
Authlib's registry holds one app and caches its clients.

Scopes are openid email profile and nothing else: neoori never calls a
provider API, so no provider token is kept.
"""
from authlib.integrations.flask_client import OAuth
from flask import current_app

from ..models.auth_identity import PROVIDERS
from . import sign_in

_EXTENSION = "authlib.integrations.flask_client"

_DISCOVERY = {
    "google": "https://accounts.google.com/.well-known/openid-configuration",
    "microsoft": "https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration",
}

# Google writes its issuer both ways, and its documentation says so.
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")

# Asked on every sign-in. select_account: job seekers often use shared
# computers (agencies, libraries), and without it the next person is signed
# in silently as the last one. Microsoft answers in the query string: a
# form_post is a cross-site POST, which does not carry the Lax session cookie
# that holds the state.
AUTHORIZE_PARAMS = {
    "google": {"prompt": "select_account"},
    "microsoft": {"prompt": "select_account", "response_mode": "query"},
}


def init_app(app) -> None:
    OAuth(app)


def client(name: str):
    """The provider's Authlib client, or None when the name is unknown or a
    key is missing (decision 13)."""
    if name not in PROVIDERS:
        return None
    client_id = current_app.config.get(f"{name.upper()}_CLIENT_ID")
    client_secret = current_app.config.get(f"{name.upper()}_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None
    oauth = current_app.extensions[_EXTENSION]
    return oauth.create_client(name) or oauth.register(
        name,
        client_id=client_id,
        client_secret=client_secret,
        server_metadata_url=_DISCOVERY[name],
        client_kwargs={
            "scope": "openid email profile",
            "code_challenge_method": "S256",
            # Discovery, JWKS and the code exchange: a hung provider must not
            # hold a gunicorn thread.
            "default_timeout": 10,
        },
    )


def configured() -> dict[str, bool]:
    return {name: client(name) is not None for name in PROVIDERS}


def claims_options(name: str, client_id: str) -> dict:
    """What the ID token must say beyond its signature, expiry and nonce,
    which Authlib checks itself: who issued it, and that it was issued to us
    (decision 6). Built fresh on every call: Authlib pops the "validate" hook
    out of the dict it is handed."""
    audience = {"essential": True, "value": client_id}
    if name == "google":
        return {"iss": {"essential": True, "values": list(GOOGLE_ISSUERS)}, "aud": audience}
    return {
        "iss": {
            "essential": True,
            "validate": lambda claims, _value: sign_in.microsoft_issuer_ok(claims),
        },
        "aud": audience,
    }

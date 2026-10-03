"""« Continuer avec Google / Microsoft », walked from /start to the landing
with the provider faked at the network boundary only (social sign-in spec,
decisions 5–13). Signature verification is the one step skipped; state,
PKCE, nonce, issuer, audience and expiry all run for real."""
import logging
import time
from unittest.mock import patch
from urllib.parse import parse_qs, quote, urlsplit

import pytest
import requests
from authlib.integrations.flask_client import FlaskOAuth2App
from authlib.oauth2.rfc7636 import create_s256_code_challenge
from authlib.oidc.core import CodeIDToken, UserInfo

from app.extensions import db
from app.models.auth_identity import AuthIdentity
from app.models.counselor_profile import CounselorProfile
from app.models.user import User
from app.services import oauth_clients, sign_in
from app.utils import auth_links

CLIENT_ID = {"google": "google-client", "microsoft": "microsoft-client"}
WORK_TENANT = "72f988bf-86f1-41af-91ab-2d7cd011db47"

METADATA = {
    "google": {
        "issuer": "https://accounts.google.com",
        "authorization_endpoint": "https://accounts.google.test/o/oauth2/v2/auth",
        "token_endpoint": "https://oauth2.google.test/token",
        "jwks_uri": "https://www.google.test/oauth2/v3/certs",
    },
    "microsoft": {
        "issuer": "https://login.microsoftonline.com/{tenantid}/v2.0",
        "authorization_endpoint": "https://login.microsoft.test/common/oauth2/v2.0/authorize",
        "token_endpoint": "https://login.microsoft.test/common/oauth2/v2.0/token",
        "jwks_uri": "https://login.microsoft.test/common/discovery/v2.0/keys",
    },
}


@pytest.fixture
def providers(app, monkeypatch):
    """Both providers configured, their discovery documents served locally."""
    app.config.update(
        GOOGLE_CLIENT_ID=CLIENT_ID["google"], GOOGLE_CLIENT_SECRET="google-secret",
        MICROSOFT_CLIENT_ID=CLIENT_ID["microsoft"], MICROSOFT_CLIENT_SECRET="microsoft-secret",
    )
    monkeypatch.setattr(FlaskOAuth2App, "load_server_metadata",
                        lambda self: dict(METADATA[self.name]))


def _cookies(res) -> str:
    return " ".join(res.headers.getlist("Set-Cookie"))


def _start(client, provider, next_path=None):
    path = f"/api/auth/{provider}/start"
    if next_path is not None:
        path += "?next=" + quote(next_path, safe="")
    return client.get(path)


def _query(res) -> dict:
    return {k: v[0] for k, v in parse_qs(urlsplit(res.headers["Location"]).query).items()}


def _id_claims(provider, nonce, **claims):
    now = int(time.time())
    base = {"aud": CLIENT_ID[provider], "iat": now, "exp": now + 600, "nonce": nonce}
    if provider == "google":
        base["iss"] = "https://accounts.google.com"
    else:
        base["iss"] = f"https://login.microsoftonline.com/{claims.get('tid', WORK_TENANT)}/v2.0"
    return {**base, **claims}


def _callback(client, provider, claims, *, state, seen=None):
    """The provider's answer: its token endpoint returns an ID token carrying
    `claims`, which Authlib's claim checks then judge with the options the
    route passed."""
    seen = seen if seen is not None else {}

    def fetch_access_token(self, **params):
        seen["token_request"] = params
        return {"access_token": "at", "token_type": "Bearer", "id_token": "unchecked"}

    def parse_id_token(self, token, nonce, claims_options=None, claims_cls=None, leeway=120):
        CodeIDToken(dict(claims), {"alg": "RS256"}, claims_options,
                    {"nonce": nonce, "client_id": self.client_id}).validate(leeway=leeway)
        return UserInfo(claims)

    with patch.object(FlaskOAuth2App, "fetch_access_token", fetch_access_token), \
            patch.object(FlaskOAuth2App, "parse_id_token", parse_id_token):
        return client.get(f"/api/auth/{provider}/callback?code=the-code&state={state}")


def _sign_in(client, provider, next_path=None, **claims):
    q = _query(_start(client, provider, next_path))
    return _callback(client, provider, _id_claims(provider, q["nonce"], **claims), state=q["state"])


# ── configuration (decision 13) ───────────────────────────────────────────────

def test_no_keys_no_buttons(client):
    assert client.get("/api/auth/providers").get_json() == {"google": False, "microsoft": False}


def test_keys_bring_the_buttons(client, providers):
    assert client.get("/api/auth/providers").get_json() == {"google": True, "microsoft": True}


def test_one_key_is_not_enough(client, app):
    app.config["GOOGLE_CLIENT_ID"] = "google-client"
    assert client.get("/api/auth/providers").get_json()["google"] is False


def test_production_sends_the_state_cookie_over_https_only():
    from app.config import Config, ProductionConfig
    assert ProductionConfig.SESSION_COOKIE_SECURE is True
    assert Config.SESSION_COOKIE_SAMESITE == "Lax"


def test_a_hung_provider_cannot_hold_a_thread(app, providers):
    assert oauth_clients.client("google").client_kwargs["default_timeout"] == 10


def test_claims_options_are_built_fresh_each_time():
    first = oauth_clients.claims_options("microsoft", "c")
    first["iss"].pop("validate")
    assert "validate" in oauth_clients.claims_options("microsoft", "c")["iss"]


# ── start (decision 5) ────────────────────────────────────────────────────────

def test_an_unconfigured_provider_is_unavailable(client):
    res = _start(client, "google")
    assert res.status_code == 302
    assert res.headers["Location"] == "/connexion?erreur=indisponible"


def test_an_unknown_provider_is_a_404(client, providers):
    assert client.get("/api/auth/apple/start").status_code == 404
    assert client.get("/api/auth/apple/callback").status_code == 404


def test_google_start_asks_for_an_account_with_pkce_and_a_nonce(client, app, providers):
    app.config["APP_URL"] = "https://neoori.tech"
    res = _start(client, "google")
    assert res.status_code == 302
    assert res.headers["Location"].startswith(METADATA["google"]["authorization_endpoint"])
    q = _query(res)
    assert q["client_id"] == "google-client"
    assert q["redirect_uri"] == "https://neoori.tech/api/auth/google/callback"
    assert q["scope"] == "openid email profile"
    assert q["prompt"] == "select_account"
    assert q["code_challenge_method"] == "S256" and q["code_challenge"]
    assert q["nonce"] and q["state"]
    assert "response_mode" not in q


def test_microsoft_answers_in_the_query_string(client, providers):
    q = _query(_start(client, "microsoft"))
    assert q["response_mode"] == "query" and q["prompt"] == "select_account"


def test_an_unreachable_provider_is_a_failure_not_a_500(client, providers, monkeypatch):
    # Review Focus 2.
    def unreachable(self):
        raise requests.ConnectionError("discovery document unreachable")
    monkeypatch.setattr(FlaskOAuth2App, "load_server_metadata", unreachable)
    res = _start(client, "google")
    assert res.status_code == 302 and res.headers["Location"] == "/connexion?erreur=echec"


# ── callback: who gets in (decisions 7–11) ────────────────────────────────────

def test_a_new_google_address_goes_on_to_finalise(client, providers):
    res = _sign_in(client, "google", sub="g-1", email="marie@gmail.com",
                   email_verified=True, given_name="Marie")
    assert res.status_code == 302 and res.headers["Location"] == "/inscription/finaliser"
    assert "access_token_cookie" not in _cookies(res)
    assert User.query.count() == 0
    ticket = auth_links.load_signup_ticket(
        client.get_cookie("signup_ticket", path="/api/auth").value).payload
    assert ticket == {"method": "google", "sub": "g-1", "email": "marie@gmail.com",
                      "prenom_hint": "Marie", "next": None}


def test_a_known_account_is_signed_in_and_sent_home(client, providers, make_user):
    make_user(email="marie@gmail.com")
    res = _sign_in(client, "google", sub="g-1", email="marie@gmail.com", email_verified=True)
    assert res.headers["Location"] == "/espace"
    assert "access_token_cookie" in _cookies(res)
    assert AuthIdentity.query.one().subject == "g-1"


@pytest.mark.parametrize("role, home", [
    ("admin", "/admin"), ("counselor", "/conseiller"), ("candidate", "/espace"),
])
def test_each_role_lands_on_its_own_home(client, providers, make_user, role, home):
    make_user(email="marie@gmail.com", role=role)
    res = _sign_in(client, "google", sub="g-1", email="marie@gmail.com", email_verified=True)
    assert res.headers["Location"] == home


def test_a_conseiller_with_a_demande_lands_on_it(client, providers, make_user):
    user = make_user(email="claire@capemploi.fr")
    db.session.add(CounselorProfile(user_id=user.id, structure="Cap Emploi 31",
                                    fonction="Conseillère", telephone="0561000000"))
    db.session.commit()
    res = _sign_in(client, "google", sub="g-1", email="claire@capemploi.fr", email_verified=True)
    assert res.headers["Location"] == "/conseiller"


def test_an_unverified_google_address_is_refused(client, providers):
    res = _sign_in(client, "google", sub="g-1", email="marie@gmail.com", email_verified=False)
    assert res.headers["Location"] == "/connexion?erreur=email_non_verifie"


def test_a_work_account_without_proof_cannot_enter_the_account_of_its_address(
        client, providers, make_user):
    """nOAuth: a tenant admin can write any address into `email`."""
    make_user(email="marie@entreprise.fr")
    res = _sign_in(client, "microsoft", sub="m-2", email="marie@entreprise.fr", tid=WORK_TENANT)
    assert res.headers["Location"] == "/connexion?erreur=email_non_verifie"
    assert AuthIdentity.query.count() == 0
    assert "access_token_cookie" not in _cookies(res)


def test_a_proven_work_address_enters(client, providers, make_user):
    make_user(email="marie@entreprise.fr")
    res = _sign_in(client, "microsoft", sub="m-2", email="marie@entreprise.fr",
                   tid=WORK_TENANT, xms_edov=True)
    assert res.headers["Location"] == "/espace"


def test_a_personal_microsoft_account_enters(client, providers, make_user):
    make_user(email="marie@outlook.fr")
    res = _sign_in(client, "microsoft", sub="m-1", email="marie@outlook.fr",
                   tid=sign_in.MSA_TENANT_ID)
    assert res.headers["Location"] == "/espace"


def test_a_provider_address_held_by_a_lookalike_is_refused(client, providers, make_user, monkeypatch):
    lookalike = make_user(email="marie@gmaïl.com", verified=False)
    monkeypatch.setattr(sign_in, "_account_at", lambda email: lookalike)
    res = _sign_in(client, "google", sub="g-1", email="marie@gmail.com", email_verified=True)
    assert res.headers["Location"] == "/connexion?erreur=email_non_verifie"
    assert AuthIdentity.query.count() == 0
    db.session.expire_all()
    assert db.session.get(User, lookalike.id).email_verified_at is None


# ── callback: the token checks (decision 6) ───────────────────────────────────

def test_a_token_naming_another_tenant_s_issuer_is_refused(client, providers, make_user):
    make_user(email="marie@outlook.fr")
    q = _query(_start(client, "microsoft"))
    claims = _id_claims("microsoft", q["nonce"], sub="m-1", email="marie@outlook.fr",
                        tid=sign_in.MSA_TENANT_ID)
    claims["iss"] = f"https://login.microsoftonline.com/{WORK_TENANT}/v2.0"
    res = _callback(client, "microsoft", claims, state=q["state"])
    assert res.headers["Location"] == "/connexion?erreur=echec"


def test_a_google_token_from_another_issuer_is_refused(client, providers, make_user):
    # Authlib falls back to the discovery document's issuer only when no
    # claims_options are passed. The route always passes them, so this check
    # is ours alone.
    make_user(email="marie@gmail.com")
    q = _query(_start(client, "google"))
    claims = _id_claims("google", q["nonce"], sub="g-1", email="marie@gmail.com",
                        email_verified=True)
    claims["iss"] = "https://evil.example"
    res = _callback(client, "google", claims, state=q["state"])
    assert res.headers["Location"] == "/connexion?erreur=echec"
    assert "access_token_cookie" not in _cookies(res)


@pytest.mark.parametrize("issuer", ["https://accounts.google.com", "accounts.google.com"])
def test_both_google_issuer_spellings_are_accepted(client, providers, make_user, issuer):
    # Google's documentation says it writes its issuer both ways. Spelled out
    # here rather than read from GOOGLE_ISSUERS, so that dropping one from the
    # tuple fails a test instead of quietly shrinking it.
    make_user(email="marie@gmail.com")
    q = _query(_start(client, "google"))
    claims = _id_claims("google", q["nonce"], sub="g-1", email="marie@gmail.com",
                        email_verified=True, iss=issuer)
    assert _callback(client, "google", claims, state=q["state"]).headers["Location"] == "/espace"


@pytest.mark.parametrize("provider", ["google", "microsoft"])
@pytest.mark.parametrize("azp", [None, "ours"])
def test_a_token_issued_to_another_app_is_refused(client, providers, make_user, provider, azp):
    # Without azp, Authlib's own authorized-party rule refuses the token before
    # our audience check matters. With azp naming us that rule is satisfied,
    # and our audience check alone stands between the token and the account.
    vouched = {
        "google": {"sub": "g-1", "email": "marie@gmail.com", "email_verified": True},
        "microsoft": {"sub": "m-1", "email": "marie@outlook.fr", "tid": sign_in.MSA_TENANT_ID},
    }[provider]
    make_user(email=vouched["email"])   # a token that got through would sign it in
    q = _query(_start(client, provider))
    extra = {"azp": CLIENT_ID[provider]} if azp == "ours" else {}
    claims = _id_claims(provider, q["nonce"], **vouched, aud="someone-else", **extra)
    res = _callback(client, provider, claims, state=q["state"])
    assert res.headers["Location"] == "/connexion?erreur=echec"
    assert "access_token_cookie" not in _cookies(res)


def test_a_token_for_another_sign_in_is_refused(client, providers, make_user):
    make_user(email="marie@gmail.com")
    q = _query(_start(client, "google"))
    claims = _id_claims("google", "another-nonce", sub="g-1", email="marie@gmail.com",
                        email_verified=True)
    assert _callback(client, "google", claims, state=q["state"]).headers["Location"] \
        == "/connexion?erreur=echec"


def test_an_expired_token_is_refused(client, providers, make_user):
    make_user(email="marie@gmail.com")
    q = _query(_start(client, "google"))
    now = int(time.time())
    claims = _id_claims("google", q["nonce"], sub="g-1", email="marie@gmail.com",
                        email_verified=True, iat=now - 4000, exp=now - 3600)
    assert _callback(client, "google", claims, state=q["state"]).headers["Location"] \
        == "/connexion?erreur=echec"


def test_the_code_exchange_carries_the_pkce_verifier(client, providers):
    q = _query(_start(client, "google"))
    seen = {}
    _callback(client, "google",
              _id_claims("google", q["nonce"], sub="g-1", email="m@gmail.com", email_verified=True),
              state=q["state"], seen=seen)
    assert create_s256_code_challenge(seen["token_request"]["code_verifier"]) == q["code_challenge"]


# ── callback: every failure is a redirect (decision 12) ───────────────────────

def test_cancelling_at_the_provider_says_so(client, providers):
    state = _query(_start(client, "google"))["state"]
    res = client.get(f"/api/auth/google/callback?error=access_denied&state={state}")
    assert res.headers["Location"] == "/connexion?erreur=annule"


def test_any_other_provider_error_is_a_failure(client, providers):
    res = client.get("/api/auth/google/callback?error=server_error")
    assert res.headers["Location"] == "/connexion?erreur=echec"


def test_a_provider_error_is_logged_and_a_cancel_is_not(client, providers, caplog):
    # Decision 12. unauthorized_client, invalid_request, a tenant's consent
    # policy: what to expect when the keys first go live, and the redirect
    # alone says nothing about which. A person's own cancel is not a fault.
    state = _query(_start(client, "google"))["state"]
    with caplog.at_level(logging.WARNING):
        caplog.clear()
        res = client.get(f"/api/auth/google/callback?error=access_denied&state={state}")
        assert res.headers["Location"] == "/connexion?erreur=annule"
        assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []

        caplog.clear()
        res = client.get("/api/auth/google/callback"
                         "?error=unauthorized_client&error_description=Client+not+allowed")
        assert res.headers["Location"] == "/connexion?erreur=echec"
        warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warnings) == 1
        message = warnings[0].getMessage()
        assert "google" in message and "unauthorized_client" in message
        assert "Client not allowed" in message


def test_a_provider_error_is_capped_and_kept_on_one_log_line(client, providers, caplog):
    # Both values are the provider's, or an attacker's forging this URL.
    with caplog.at_level(logging.WARNING):
        client.get("/api/auth/google/callback?error=" + "q" * 150
                   + "&error_description=first%0Asecond" + "z" * 400)
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(warnings) == 1
    message = warnings[0].getMessage()
    assert "q" * 100 in message and "q" * 101 not in message
    # The description's cap is 300 characters, 12 of them "first\nsecond".
    assert "z" * 288 in message and "z" * 289 not in message
    assert "\n" not in message


@pytest.mark.parametrize("query", ["?code=c&state=never-issued", "?code=c", ""])
def test_a_callback_without_a_live_state_is_a_failure_not_a_500(client, providers, query):
    # Review Focus 2: a bookmark, a second tab, a lost session cookie.
    res = client.get(f"/api/auth/google/callback{query}")
    assert res.status_code == 302 and res.headers["Location"] == "/connexion?erreur=echec"


def test_a_callback_replayed_with_back_is_a_failure(client, providers, make_user):
    # Review Focus 2.
    make_user(email="marie@gmail.com")
    q = _query(_start(client, "google"))
    claims = _id_claims("google", q["nonce"], sub="g-1", email="marie@gmail.com",
                        email_verified=True)
    assert _callback(client, "google", claims, state=q["state"]).headers["Location"] == "/espace"
    assert _callback(client, "google", claims, state=q["state"]).headers["Location"] \
        == "/connexion?erreur=echec"


def test_a_failure_while_resolving_is_a_failure_not_a_500(client, providers, monkeypatch):
    def broken(*args):
        raise RuntimeError("database unavailable")
    monkeypatch.setattr(sign_in, "resolve_oauth", broken)
    res = _sign_in(client, "google", sub="g-1", email="m@gmail.com", email_verified=True)
    assert res.headers["Location"] == "/connexion?erreur=echec"


@pytest.mark.parametrize("sub", ["x" * 256, "sujet-é", ""])
def test_an_unusable_subject_is_a_failure_and_links_nothing(client, providers, make_user, sub):
    make_user(email="marie@gmail.com")
    res = _sign_in(client, "google", sub=sub, email="marie@gmail.com", email_verified=True)
    assert res.headers["Location"] == "/connexion?erreur=echec"
    assert AuthIdentity.query.count() == 0
    assert "access_token_cookie" not in _cookies(res)
    assert client.get_cookie("signup_ticket", path="/api/auth") is None


# ── next (decision 5) ─────────────────────────────────────────────────────────

def test_the_destination_survives_the_round_trip_byte_for_byte(client, providers, make_user):
    # Review Focus 5.
    make_user(email="marie@gmail.com")
    destination = "/analyse/nouveau?parcours=2&x=a%20b"
    res = _sign_in(client, "google", next_path=destination, sub="g-1",
                   email="marie@gmail.com", email_verified=True)
    assert res.headers["Location"] == destination


def test_an_unsafe_destination_is_dropped_at_start(client, providers, make_user):
    make_user(email="marie@gmail.com")
    res = _sign_in(client, "google", next_path="//evil.com", sub="g-1",
                   email="marie@gmail.com", email_verified=True)
    assert res.headers["Location"] == "/espace"


def test_the_destination_reaches_the_ticket(client, providers):
    _sign_in(client, "google", next_path="/analyse/nouveau", sub="g-1",
             email="marie@gmail.com", email_verified=True)
    ticket = auth_links.load_signup_ticket(
        client.get_cookie("signup_ticket", path="/api/auth").value).payload
    assert ticket["next"] == "/analyse/nouveau"

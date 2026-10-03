"""Who a sign-in is and which account it enters (social sign-in spec,
decisions 3, 7–9 and 18)."""
from datetime import datetime
from unittest.mock import patch

import pytest

from app.extensions import db
from app.models.auth_identity import AuthIdentity
from app.models.profile import CONSENT_VERSION, Profile
from app.models.user import User
from app.routes.auth import password_matches
from app.services import sign_in
from app.utils import auth_links

NOTIFY = "app.services.demande_mail.notify_if_visible"
WORK_TENANT = "72f988bf-86f1-41af-91ab-2d7cd011db47"

GOOGLE = {"sub": "g-1", "email": "marie@gmail.com", "email_verified": True}
MS_PERSONAL = {"sub": "m-1", "email": "marie@outlook.fr", "tid": sign_in.MSA_TENANT_ID}
MS_WORK = {"sub": "m-2", "email": "marie@entreprise.fr", "tid": WORK_TENANT}


def _fresh(user):
    db.session.expire_all()
    return db.session.get(User, user.id)


def _ticket_in(response) -> dict:
    header = next(h for h in response.headers.getlist("Set-Cookie")
                  if h.startswith("signup_ticket="))
    return auth_links.load_signup_ticket(header.split(";", 1)[0].split("=", 1)[1]).payload


# ── the unusable hash (decision 3) ────────────────────────────────────────────

def test_no_password_opens_a_password_less_account(app):
    user = User(email="sans@test.fr", password_hash=sign_in.unusable_password_hash())
    for guess in ("", "motdepasse1", "None", user.password_hash):
        assert password_matches(user, guess) is False


def test_each_unusable_hash_is_new(app):
    assert sign_in.unusable_password_hash() != sign_in.unusable_password_hash()


# ── trust (decision 7) ────────────────────────────────────────────────────────

def test_google_vouches_only_for_a_verified_address():
    assert sign_in.trusted_email("google", GOOGLE) == "marie@gmail.com"
    for flag in (False, None, "true", 1):
        assert sign_in.trusted_email("google", {**GOOGLE, "email_verified": flag}) is None


def test_a_personal_microsoft_account_is_trusted():
    assert sign_in.trusted_email("microsoft", MS_PERSONAL) == "marie@outlook.fr"


def test_a_work_account_needs_its_domain_proven():
    """nOAuth: a tenant admin can write any address into `email`."""
    assert sign_in.trusted_email("microsoft", MS_WORK) is None


@pytest.mark.parametrize("flag", [True, "1", "true", "TRUE"])
def test_xms_edov_proves_a_work_address_in_every_form_microsoft_sends(flag):
    claims = {**MS_WORK, "xms_edov": flag}
    assert sign_in.trusted_email("microsoft", claims) == "marie@entreprise.fr"


@pytest.mark.parametrize("flag", [False, "0", "false", None, 1, ""])
def test_anything_else_is_no_proof(flag):
    assert sign_in.trusted_email("microsoft", {**MS_WORK, "xms_edov": flag}) is None


@pytest.mark.parametrize("email", [None, "", "pas-une-adresse", "\ud800@outlook.fr"])
def test_no_usable_address_is_no_trusted_address(email):
    assert sign_in.trusted_email("microsoft", {**MS_PERSONAL, "email": email}) is None


def test_a_phone_only_microsoft_account_has_no_address():
    claims = {k: v for k, v in MS_PERSONAL.items() if k != "email"}
    assert sign_in.trusted_email("microsoft", claims) is None


def test_a_trusted_address_comes_back_in_its_stored_form():
    claims = {**MS_PERSONAL, "email": " Marie.Dupont@Outlook.FR "}
    assert sign_in.trusted_email("microsoft", claims) == "marie.dupont@outlook.fr"


def test_an_unknown_provider_vouches_for_nothing():
    assert sign_in.trusted_email("apple", GOOGLE) is None


# ── the Microsoft issuer (decision 6) ─────────────────────────────────────────

def test_the_issuer_must_name_the_token_s_own_tenant():
    tid = WORK_TENANT
    assert sign_in.microsoft_issuer_ok(
        {"tid": tid, "iss": f"https://login.microsoftonline.com/{tid}/v2.0"})
    assert not sign_in.microsoft_issuer_ok(
        {"tid": tid, "iss": f"https://login.microsoftonline.com/{sign_in.MSA_TENANT_ID}/v2.0"})
    assert not sign_in.microsoft_issuer_ok(
        {"tid": tid, "iss": "https://login.microsoftonline.com/{tenantid}/v2.0"})
    assert not sign_in.microsoft_issuer_ok({"iss": "https://login.microsoftonline.com//v2.0"})
    assert not sign_in.microsoft_issuer_ok({"tid": 5, "iss": "https://login.microsoftonline.com/5/v2.0"})


# ── entering an account (decision 9) ──────────────────────────────────────────

def test_entering_a_verified_account_keeps_its_password(app, make_user):
    user = make_user(email="marie@gmail.com")
    with patch(NOTIFY) as told:
        sign_in.enter(user, "google", "g-1")
    assert password_matches(_fresh(user), "motdepasse1")
    assert AuthIdentity.query.filter_by(user_id=user.id, provider="google", subject="g-1").count() == 1
    told.assert_not_called()


def test_entering_twice_links_once(app, make_user):
    user = make_user()
    sign_in.enter(user, "google", "g-1")
    sign_in.enter(user, "google", "g-1")
    assert AuthIdentity.query.count() == 1


def test_entering_an_unverified_account_wipes_the_password_a_stranger_set(app, make_user):
    user = make_user(verified=False)
    reset_token = auth_links.make_reset_token(user)
    with patch(NOTIFY) as told:
        sign_in.enter(user, "google", "g-1")
    fresh = _fresh(user)
    assert fresh.email_verified_at is not None
    assert not password_matches(fresh, "motdepasse1")
    # pwv moved with the hash: the stranger's reset link died too.
    assert (auth_links.load_reset_token(reset_token).payload["pwv"]
            != auth_links.password_fingerprint(fresh.password_hash))
    told.assert_called_once()


def test_the_profile_seed_survives_the_wipe(app, make_user):
    user = make_user(verified=False)
    db.session.add(Profile(user_id=user.id, prenom="Marie", tranche_age="25_34",
                           consent_at=datetime.utcnow(), consent_version=CONSENT_VERSION))
    db.session.commit()
    with patch(NOTIFY):
        sign_in.enter(user)
    assert Profile.query.filter_by(user_id=user.id).one().prenom == "Marie"


# ── resolution (decision 8) ───────────────────────────────────────────────────

def test_a_known_identity_wins_over_a_changed_address(app, make_user):
    user = make_user(email="ancienne@gmail.com")
    db.session.add(AuthIdentity(user_id=user.id, provider="google", subject="g-1"))
    db.session.commit()
    outcome = sign_in.resolve_oauth("google", {**GOOGLE, "email": "nouvelle@gmail.com"})
    assert outcome.kind == "user" and outcome.user.id == user.id


def test_a_known_identity_enters_without_a_trusted_address(app, make_user):
    user = make_user(email="marie@entreprise.fr")
    db.session.add(AuthIdentity(user_id=user.id, provider="microsoft", subject="m-2"))
    db.session.commit()
    outcome = sign_in.resolve_oauth("microsoft", MS_WORK)
    assert outcome.kind == "user" and outcome.user.id == user.id


def test_a_trusted_address_enters_its_account_and_links_it(app, make_user):
    user = make_user(email="marie@gmail.com")
    outcome = sign_in.resolve_oauth("google", GOOGLE)
    assert outcome.kind == "user" and outcome.user.id == user.id
    assert AuthIdentity.query.filter_by(provider="google", subject="g-1").one().user_id == user.id


def test_a_trusted_address_without_an_account_is_a_signup(app):
    outcome = sign_in.resolve_oauth("google", GOOGLE)
    assert outcome == sign_in.Outcome("signup", email="marie@gmail.com")
    assert User.query.count() == 0 and AuthIdentity.query.count() == 0


def test_an_untrusted_address_is_refused_and_links_nothing(app, make_user):
    make_user(email="marie@entreprise.fr")
    assert sign_in.resolve_oauth("microsoft", MS_WORK).kind == "refused"
    assert AuthIdentity.query.count() == 0


def test_a_provider_address_in_capitals_enters_the_lowercase_account(app, make_user):
    # Review Focus 1.
    user = make_user(email="marie.dupont@outlook.fr")
    outcome = sign_in.resolve_oauth("microsoft", {**MS_PERSONAL, "email": "Marie.Dupont@Outlook.fr"})
    assert outcome.kind == "user" and outcome.user.id == user.id
    assert User.query.count() == 1


def test_an_address_alone_enters_without_linking_anything(app, make_user):
    user = make_user(email="marie@test.fr")
    assert sign_in.existing_account(None, None, "marie@test.fr").id == user.id
    assert AuthIdentity.query.count() == 0


def test_an_address_that_only_collates_equal_is_not_entered(app, make_user, monkeypatch):
    # MySQL's utf8mb4_unicode_ci files « jean@société.fr » under
    # « jean@societe.fr »; SQLite cannot, so the lookup is stood in for.
    lookalike = make_user(email="jean@société.fr")
    monkeypatch.setattr(sign_in, "_account_at", lambda email: lookalike)
    assert sign_in.existing_account(None, None, "jean@societe.fr") is None
    assert sign_in.address_in_use("jean@societe.fr") is True
    assert AuthIdentity.query.count() == 0


def test_a_provider_sign_in_onto_a_lookalike_address_is_refused(app, make_user, monkeypatch):
    lookalike = make_user(email="marie@gmaïl.com", verified=False)
    monkeypatch.setattr(sign_in, "_account_at", lambda email: lookalike)
    assert sign_in.resolve_oauth("google", GOOGLE).kind == "refused"
    assert AuthIdentity.query.count() == 0
    fresh = _fresh(lookalike)
    assert fresh.email_verified_at is None          # not verified by someone else's proof
    assert password_matches(fresh, "motdepasse1")   # and its password untouched


def test_a_legacy_address_in_capitals_is_still_entered(app, make_user, monkeypatch):
    legacy = make_user(email="Marie@Gmail.com")     # stored before register lowercased
    monkeypatch.setattr(sign_in, "_account_at", lambda email: legacy)
    outcome = sign_in.resolve_oauth("google", GOOGLE)
    assert outcome.kind == "user" and outcome.user.id == legacy.id


def test_account_of_names_only_the_account_of_that_address(app, make_user, monkeypatch):
    lookalike = make_user(email="jean@société.fr")
    monkeypatch.setattr(sign_in, "_account_at", lambda email: lookalike)
    assert sign_in.account_of("jean@societe.fr") is None
    assert sign_in.account_of("jean@société.fr").id == lookalike.id


def test_a_free_address_is_not_in_use(app):
    assert sign_in.address_in_use("personne@test.fr") is False


# ── the signup ticket (decision 18) ───────────────────────────────────────────

def test_the_ticket_cookie_is_scoped_and_hidden_from_scripts(app):
    response = app.response_class()
    sign_in.set_signup_ticket(response, method="google", sub="g-1",
                              email="marie@gmail.com", prenom_hint="Marie")
    cookie = response.headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "Path=/api/auth" in cookie
    assert "SameSite=Lax" in cookie and "Max-Age=1800" in cookie
    assert _ticket_in(response)["prenom_hint"] == "Marie"


def test_the_prenom_hint_is_trimmed_to_what_the_profile_holds(app):
    # Review Focus 4: a longer name would prefill a form that can never be sent.
    response = app.response_class()
    sign_in.set_signup_ticket(response, method="google", sub="g-1",
                              email="m@gmail.com", prenom_hint="  " + "M" * 300)
    assert _ticket_in(response)["prenom_hint"] == "M" * 120


def test_a_missing_hint_is_an_empty_prenom(app):
    response = app.response_class()
    sign_in.set_signup_ticket(response, method="microsoft", sub="m-1",
                              email="m@outlook.fr", prenom_hint=None)
    assert _ticket_in(response)["prenom_hint"] == ""


def test_an_unencodable_hint_is_dropped(app):
    response = app.response_class()
    sign_in.set_signup_ticket(response, method="google", sub="g-1",
                              email="m@gmail.com", prenom_hint="Ma\ud800rie")
    assert _ticket_in(response)["prenom_hint"] == ""


def test_clearing_the_ticket_expires_the_cookie(app):
    response = app.response_class()
    sign_in.clear_signup_ticket(response)
    cookie = response.headers["Set-Cookie"]
    assert cookie.startswith("signup_ticket=;") and "Path=/api/auth" in cookie


def test_a_live_ticket_is_read_from_the_request(app):
    token = auth_links.make_signup_ticket(method="email", sub=None, email="m@test.fr")
    with app.test_request_context("/", headers={"Cookie": f"signup_ticket={token}"}):
        ticket, code = sign_in.live_signup_ticket()
    assert code is None and ticket["email"] == "m@test.fr"


@pytest.mark.parametrize("payload", [
    dict(method="apple", sub="a-1", email="m@icloud.com"),
    dict(method="google", sub=None, email="m@gmail.com"),
    dict(method="google", sub="", email="m@gmail.com"),
    dict(method="email", sub=None, email=""),
])
def test_a_signed_but_malformed_ticket_is_invalid(app, payload):
    token = auth_links.make_signup_ticket(**payload)
    with app.test_request_context("/", headers={"Cookie": f"signup_ticket={token}"}):
        assert sign_in.live_signup_ticket() == (None, "link_invalid")


def test_no_ticket_is_an_invalid_one(app):
    with app.test_request_context("/"):
        assert sign_in.live_signup_ticket() == (None, "link_invalid")

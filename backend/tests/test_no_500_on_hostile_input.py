"""Every body-reading route, fuzzed with hostile JSON, table-driven.

Why this test exists: four separate unhandled-500 vectors of this exact
class reached production (a non-string auth password crashing bcrypt, a
non-dict analyses.inputs crashing dict(), non-string profile fields crashing
.strip(), a non-string payments id crashing get_or_404's query). Fuzzing the
routes systematically -- rather than trusting a per-bug regression test --
is what turned up the last of those four, plus several more of the same
shape that had never been reported: a non-string "tier" crashing
services.tiers.normalize, a non-string analyses "draft_id" crashing a
filter_by() query, non-string values inside analyses.inputs (cv_text,
cible_visee, and the parcours 2/3 free-text fields) crashing their
validators, a non-hashable inputs._path crashing
services.section_registry.normalize's `in` check, and a non-bool
prompts.create_prompt "activate" crashing the strict SQLite Boolean column
it was written to unconverted. All are fixed; this test is what keeps the
class fixed. Adding a route means adding one row to ROUTES below -- the
fuzz then runs automatically against it.

voyage.py is deliberately not in ROUTES: every body-reading route there
already guards isinstance(data, dict) and isinstance(field, str) from an
earlier hardening pass (see the inline comments in that file), and this
task's scope excludes editing it. Upload routes (multipart file bodies, not
JSON) are out of scope for the same reason a GET is: they never read
request.get_json().

Contract: 5xx is a failure, an escaped exception is a failure (Flask's
TESTING=True re-raises unhandled exceptions into the test rather than
turning them into a 500 response, so a crash here surfaces as a pytest
error, not just a status code), 4xx is a pass. This test never asserts an
exact status code -- that is what the dedicated per-route tests are for.
"""
import copy
from datetime import datetime

import pytest
from flask_jwt_extended import create_access_token

from app.extensions import bcrypt as _bcrypt
from app.extensions import db as _db
from app.models.analysis import Analysis
from app.models.profile import Profile
from app.models.user import User

# The real password behind rig["candidate_email"] -- see _user()'s docstring
# on why the candidate (and only the candidate) needs a genuine bcrypt hash.
CANDIDATE_PASSWORD = "RigCandidatePassw0rd!"

# A JSON array, a bare string, a bare number, a bare bool and JSON null: five
# ways a body can be valid JSON but not the dict every route expects.
HOSTILE_BODIES = [[1, 2, 3], "a string", 42, True, None]

# Bytes that are not valid JSON at all -- request.get_json(silent=True)
# returns None for this, exercised once per route rather than per-value.
NON_JSON_PAYLOAD = b"{not valid json at all"

# Hostile values for a single field: an int, a bool, a non-empty list, a
# non-empty dict, a float, and None (present but null).
HOSTILE_VALUES = [5, True, [1, 2], {"a": 1}, 0.5, None]


def _user(email, role="candidate", password_hash="x"):
    """password_hash="x" is the placeholder every other test file in this
    suite uses -- fine there, since none of them log in as that user. The
    login row below does, so its candidate gets a real hash instead (see
    `rig`): bcrypt.check_password_hash raises ValueError("Invalid salt") for
    "x", which would look like a fixture bug wearing this test's clothes."""
    user = User(email=email, password_hash=password_hash, role=role)
    _db.session.add(user)
    _db.session.commit()
    return user


def _headers(user):
    token = create_access_token(identity=str(user.id), additional_claims={"role": user.role})
    return {"Authorization": f"Bearer {token}"}


def _analysis(owner=None, **overrides):
    fields = {
        "user_id": owner.id if owner else None,
        "inputs": {"_path": "1", "cv_text": "x" * 250, "cible_visee": "y" * 60},
        "status": "success",
    }
    fields.update(overrides)
    a = Analysis(**fields)
    _db.session.add(a)
    _db.session.commit()
    return a


@pytest.fixture
def rig(client, app, monkeypatch):
    """Everything the route table's rows need to reach their body-reading
    code, not bounce off an earlier gate.

    STRIPE_SECRET_KEY is set so /api/payments/* runs its real body-reading
    code instead of the legitimate "Stripe not configured" 503 -- that 503
    would be indistinguishable from the crash this test exists to catch, and
    the task this file was written for was explicit: assert 503 is not what
    a properly-guarded route returns once a key is configured.

    stripe.checkout.Session.create/.retrieve are monkeypatched to stubs: a
    field combination can be hostile in shape yet still valid enough to sail
    past every guard (e.g. an absent/null "tier" on checkout legitimately
    defaults to "paid" -- that is a real path, not a bug), and letting that
    reach the real Stripe SDK with a fake key raises stripe.AuthenticationError
    from a network call, which is a test-harness artifact, not a route crash.
    The stub still requires a string id, the same way the real SDK's URL
    building does (it string-formats the id into a path) -- so a route that
    forwards a non-string session_id/analysis_id to Stripe still fails here,
    the way it would against the real API.

    The candidate gets a pre-existing, already-consented Profile so
    PUT /api/profile fuzzing exercises the field-assignment code: the
    "consentement requis" gate only fires while creating a first profile,
    so an update on a fresh account would otherwise mask everything below it.

    create_analysis's own start_analysis is patched out, same as
    test_parcours_inputs.py does for any real (non-error) POST: fuzzing a
    single field can otherwise still leave the rest of "inputs" valid, which
    spawns the real background generation thread against a promptless test
    DB whose connection this test has already torn down by the time it runs.
    """
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_dummy")
    monkeypatch.setattr("app.routes.analyses.start_analysis", lambda *a, **kw: None)

    import stripe

    class _FakeSession:
        id = "cs_test_fuzz_session"
        url = "https://stripe.test/session"
        payment_status = "paid"
        metadata = {}

        def __getitem__(self, key):
            return getattr(self, key)

    def _fake_create(**kwargs):
        return _FakeSession()

    def _fake_retrieve(session_id, *args, **kwargs):
        if not isinstance(session_id, str):
            # Mirrors the real SDK: it string-formats the id into a URL path,
            # so a non-string id never reaches Stripe as a clean 4xx -- it
            # raises before any request is sent.
            raise TypeError("id must be a string, not " + type(session_id).__name__)
        return _FakeSession()

    monkeypatch.setattr(stripe.checkout.Session, "create", staticmethod(_fake_create))
    monkeypatch.setattr(stripe.checkout.Session, "retrieve", staticmethod(_fake_retrieve))

    # rounds=4 (bcrypt's minimum): this only needs to be a real, parseable
    # hash, not a secure one -- and it runs once per test in this file.
    real_hash = _bcrypt.generate_password_hash(CANDIDATE_PASSWORD, rounds=4).decode("utf-8")
    candidate = _user("fuzz-candidate@test.fr", password_hash=real_hash)
    admin = _user("fuzz-admin@test.fr", role="admin")
    counselor = _user("fuzz-counselor@test.fr", role="counselor")

    profile = Profile(user_id=candidate.id, prenom="Rig")
    profile.consent_at = datetime.utcnow()
    profile.consent_version = "v1.2"
    _db.session.add(profile)
    _db.session.commit()

    analysis = _analysis(share_token="fuzz-share-token")

    return {
        "candidate_headers": _headers(candidate),
        "admin_headers": _headers(admin),
        "counselor_headers": _headers(counselor),
        "candidate_email": candidate.email,
        "admin_id": admin.id,
        "analysis_id": analysis.id,
        "share_token": analysis.share_token,
    }


def _set(body: dict, field: str, value) -> None:
    """Set `field` on body. One level of dotted nesting is supported
    (e.g. "inputs.cv_text") so a sub-field of a JSON body field can be
    fuzzed while its siblings stay at their valid baseline value."""
    if "." in field:
        parent, child = field.split(".", 1)
        nested = body.get(parent)
        if not isinstance(nested, dict):
            nested = {}
            body[parent] = nested
        nested[child] = value
    else:
        body[field] = value


# ── the route table ───────────────────────────────────────────────────────────
# (name, method, path, headers, base body, fields to fuzz). `base` is the
# minimal valid body needed to reach every listed field's code -- some
# fields only crash past another field's own gate (e.g. auth's password is
# only reachable with a non-empty email already present).
ROUTES = [
    dict(
        name="register",
        method="post",
        path=lambda rig: "/api/auth/register",
        headers=lambda rig: {},
        base=lambda rig: {"email": "fuzz-register@test.fr", "password": "ValidPassw0rd1"},
        fields=["email", "password"],
    ),
    dict(
        name="login",
        method="post",
        path=lambda rig: "/api/auth/login",
        headers=lambda rig: {},
        # An *existing* user's email: bcrypt.check_password_hash only runs
        # (and so only sees a hostile "password") once a user is found --
        # `if not user or not bcrypt...` short-circuits past it for an
        # unknown email, which would hide the password vector entirely.
        base=lambda rig: {"email": rig["candidate_email"], "password": "whatever12"},
        fields=["email", "password"],
    ),
    dict(
        name="create_analysis",
        method="post",
        path=lambda rig: "/api/analyses/",
        headers=lambda rig: {},
        base=lambda rig: {
            "inputs": {"_path": "1", "cv_text": "x" * 250, "cible_visee": "y" * 60},
            "tier": "free",
        },
        fields=[
            "inputs", "tier",
            "inputs.cv_text", "inputs.cible_visee", "inputs._path", "inputs._chemin",
        ],
    ),
    dict(
        name="save_draft",
        method="post",
        path=lambda rig: "/api/analyses/draft",
        headers=lambda rig: rig["candidate_headers"],
        base=lambda rig: {"inputs": {"_path": "1"}, "draft_id": None},
        fields=["inputs", "draft_id"],
    ),
    dict(
        name="unlock_with_code",
        method="post",
        path=lambda rig: f"/api/analyses/{rig['analysis_id']}/unlock",
        headers=lambda rig: {},
        base=lambda rig: {"code": "AAAA1111"},
        fields=["code"],
    ),
    dict(
        name="price_feedback",
        method="post",
        path=lambda rig: f"/api/analyses/{rig['analysis_id']}/price-feedback",
        headers=lambda rig: {},
        base=lambda rig: {"bucket": "5_10", "useful": True},
        fields=["bucket", "useful"],
    ),
    dict(
        name="upsert_profile",
        method="put",
        path=lambda rig: "/api/profile",
        headers=lambda rig: rig["candidate_headers"],
        base=lambda rig: {
            "consent": True,
            "prenom": "Test", "nom": "Test", "ville": "Lyon",
            "projet": "un projet", "projet_document": "", "contraintes_pratiques": "",
            "rayon": "ma_ville", "tranche_age": "25_34", "situation": "en_poste_evolution",
            "conditions": {}, "oeth": False,
        },
        fields=[
            "prenom", "nom", "ville", "projet", "projet_document", "contraintes_pratiques",
            "rayon", "tranche_age", "situation", "reconversion_scope",
            "conditions", "oeth",
        ],
    ),
    dict(
        name="checkout",
        method="post",
        path=lambda rig: "/api/payments/checkout",
        headers=lambda rig: {},
        base=lambda rig: {"analysis_id": rig["analysis_id"], "tier": "paid"},
        fields=["analysis_id", "tier"],
    ),
    dict(
        name="verify",
        method="post",
        path=lambda rig: "/api/payments/verify",
        headers=lambda rig: {},
        base=lambda rig: {"session_id": "cs_test_fuzz"},
        fields=["session_id"],
    ),
    dict(
        name="admin_set_role",
        method="put",
        path=lambda rig: f"/api/admin/users/{rig['admin_id']}/role",
        headers=lambda rig: rig["admin_headers"],
        base=lambda rig: {"role": "candidate"},
        fields=["role"],
    ),
    dict(
        name="admin_create_counselor_code",
        method="post",
        path=lambda rig: "/api/admin/counselor-codes",
        headers=lambda rig: rig["admin_headers"],
        base=lambda rig: {"label": "fuzz-label"},
        fields=["label"],
    ),
    dict(
        name="create_prompt",
        method="post",
        path=lambda rig: "/api/prompts/",
        headers=lambda rig: rig["admin_headers"],
        base=lambda rig: {
            "version_label": "v-fuzz", "system_prompt_text": "texte valide",
            "path": "1", "activate": False,
        },
        fields=["version_label", "system_prompt_text", "path", "activate"],
    ),
    dict(
        name="upsert_counselor_notes",
        method="put",
        path=lambda rig: f"/api/c/{rig['share_token']}/notes",
        headers=lambda rig: rig["counselor_headers"],
        base=lambda rig: {"body": "note de test"},
        fields=["body"],
    ),
]

PAYMENT_ROUTE_NAMES = {"checkout", "verify"}


def _call(client, route, rig, *, body=..., raw=None):
    method = getattr(client, route["method"])
    path = route["path"](rig)
    headers = dict(route["headers"](rig))
    if raw is not None:
        headers["Content-Type"] = "application/json"
        return client.open(path, method=route["method"].upper(), data=raw, headers=headers)
    return method(path, json=body, headers=headers)


@pytest.mark.parametrize("route", ROUTES, ids=lambda r: r["name"])
@pytest.mark.parametrize("body", HOSTILE_BODIES, ids=lambda b: repr(b))
def test_hostile_body_never_crashes(client, rig, route, body):
    res = _call(client, route, rig, body=body)
    assert res.status_code < 500, f"{route['name']}: {res.status_code} for body {body!r}"
    if route["name"] in PAYMENT_ROUTE_NAMES:
        assert res.status_code != 503, f"{route['name']}: 503 masked the crash check"


@pytest.mark.parametrize("route", ROUTES, ids=lambda r: r["name"])
def test_non_json_payload_never_crashes(client, rig, route):
    res = _call(client, route, rig, raw=NON_JSON_PAYLOAD)
    assert res.status_code < 500, f"{route['name']}: {res.status_code} for a non-JSON payload"


@pytest.mark.parametrize("route", ROUTES, ids=lambda r: r["name"])
@pytest.mark.parametrize("value", HOSTILE_VALUES, ids=lambda v: repr(v))
def test_hostile_field_value_never_crashes(client, rig, route, value):
    for field in route["fields"]:
        body = copy.deepcopy(route["base"](rig))
        _set(body, field, value)
        res = _call(client, route, rig, body=body)
        assert res.status_code < 500, (
            f"{route['name']}: field={field!r} value={value!r} -> {res.status_code}"
        )
        if route["name"] in PAYMENT_ROUTE_NAMES:
            assert res.status_code != 503, (
                f"{route['name']}: field={field!r} value={value!r} -> 503 masked the crash check"
            )

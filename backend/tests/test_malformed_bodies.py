"""Malformed request bodies must hit the route's existing validation, never crash.

Two defect classes were live in production. Class A:
`request.get_json(silent=True) or {}` lets a JSON array, string or number
survive as truthy, so the caller's `.get(...)` raised AttributeError -- an
unhandled 500 where the route meant to answer 400. Class B: a field read as
`(data.get(field) or "").strip()` raised the same way when the field was
present but a truthy non-string (an int, a non-empty list/dict, `True`).

Class C (the counselor's private note, `PUT /api/counselor/analyses/<id>/notes`;
before the four-doors spec, `PUT /api/c/<token>/notes`) had a third defect on
top of class A: a malformed body didn't just avoid crashing, it silently
cleared the counselor's stored note and reported success. The tests at the
bottom of this file assert the note's text from a fresh DB query after every
malformed request, because that is the whole point of the fix -- the data must
survive.
"""
import pytest
from flask_jwt_extended import create_access_token

from app.extensions import db as _db
from app.models.analysis import Analysis
from app.models.counselor_note import CounselorNote
from app.models.user import User
from tests.helpers_doors import counselor as _approved_counselor

# A JSON array, a bare JSON string and a bare JSON number: each is valid,
# truthy JSON that is not a dict.
MALFORMED_BODIES = [[1, 2, 3], "a string", 42]

# Truthy non-string values for a single field: int, non-empty dict, bool.
# (An empty list/dict is falsy and was never the crashing case.)
NON_STRING_VALUES = [5, {"nested": "x"}, True]


def _user(email, role="candidate"):
    user = User(email=email, password_hash="x", role=role)
    _db.session.add(user)
    _db.session.commit()
    return user


def _headers(user):
    token = create_access_token(identity=str(user.id), additional_claims={"role": user.role})
    return {"Authorization": f"Bearer {token}"}


def _analysis(owner=None, **overrides):
    fields = {
        "user_id": owner.id if owner else None,
        "inputs": {"_path": "1", "cv_text": "x" * 250, "cible_visee": "x" * 60},
        "status": "success",
    }
    fields.update(overrides)
    a = Analysis(**fields)
    _db.session.add(a)
    _db.session.commit()
    return a


@pytest.fixture
def candidate(app):
    return _user("malformed-candidate@test.fr")


@pytest.fixture
def auth(candidate):
    return _headers(candidate)


# ── class A: a non-dict body must reach the route's own validation ───────────

@pytest.mark.parametrize("body", MALFORMED_BODIES)
def test_register_survives_malformed_body(client, body):
    res = client.post("/api/auth/register", json=body)
    assert res.status_code != 500
    assert res.status_code == 400
    assert res.get_json()["error"] == "Email et mot de passe requis."


@pytest.mark.parametrize("body", MALFORMED_BODIES)
def test_login_survives_malformed_body(client, body):
    res = client.post("/api/auth/login", json=body)
    assert res.status_code != 500
    # login has no dedicated "malformed input" branch -- an empty/unknown
    # email falls straight through to the ordinary "no such user" answer.
    assert res.status_code == 401
    assert res.get_json()["error"] == "Identifiants incorrects."


@pytest.mark.parametrize("body", MALFORMED_BODIES)
def test_create_analysis_survives_malformed_body(client, auth, body):
    res = client.post("/api/analyses/", json=body, headers=auth)
    assert res.status_code != 500
    assert res.status_code == 400
    assert "errors" in res.get_json()


@pytest.mark.parametrize("body", MALFORMED_BODIES)
def test_save_draft_survives_malformed_body(client, auth, body):
    """save_draft never validated its inputs -- a malformed body coerces to
    {} and produces an empty draft, exactly what an explicit {} body already
    did. The invariant this guards is "never crashes"; this particular route
    has no 4xx path to land on."""
    res = client.post("/api/analyses/draft", json=body, headers=auth)
    assert res.status_code != 500
    assert res.status_code == 201
    assert res.get_json()["analysis"]["inputs"] == {}


@pytest.mark.parametrize("body", MALFORMED_BODIES)
def test_unlock_with_code_survives_malformed_body(client, candidate, auth, body):
    # /unlock answers 401 / 403 before it reads the body unless the caller owns
    # the analysis: the owner's bearer header keeps the body what is tested.
    a = _analysis(owner=candidate)
    res = client.post(f"/api/analyses/{a.id}/unlock", json=body, headers=auth)
    assert res.status_code != 500
    assert res.status_code == 400
    assert res.get_json()["error"] == "Code requis."


@pytest.mark.parametrize("body", MALFORMED_BODIES)
def test_price_feedback_survives_malformed_body(client, candidate, auth, body):
    # The probe answers 403 before it reads the body unless the caller may read
    # the report: the owner's bearer header keeps the body what is tested.
    a = _analysis(owner=candidate)
    res = client.post(f"/api/analyses/{a.id}/price-feedback", json=body, headers=auth)
    assert res.status_code != 500
    assert res.status_code == 400
    assert res.get_json()["error"] == "Réponse invalide."


@pytest.mark.parametrize("body", MALFORMED_BODIES)
def test_create_counselor_code_survives_malformed_body(client, body, admin_headers):
    res = client.post("/api/admin/counselor-codes", json=body, headers=admin_headers)
    assert res.status_code != 500
    assert res.status_code == 400
    assert res.get_json()["error"] == "label requis."


@pytest.mark.parametrize("body", MALFORMED_BODIES)
def test_upsert_profile_survives_malformed_body(client, auth, body):
    res = client.put("/api/profile", json=body, headers=auth)
    assert res.status_code != 500
    assert res.status_code == 400
    assert res.get_json()["errors"] == ["Le consentement est requis."]


@pytest.mark.parametrize("body", MALFORMED_BODIES)
def test_save_counselor_note_survives_malformed_body(client, body):
    counselor = _approved_counselor("notes-malformed@test.fr")
    a = _analysis(door="advisor", counselor_id=counselor.id)
    res = client.put(f"/api/counselor/analyses/{a.id}/notes", json=body, headers=_headers(counselor))
    assert res.status_code != 500
    assert res.status_code == 400
    assert res.get_json()["error"] == "Note invalide."


@pytest.mark.parametrize("body", MALFORMED_BODIES)
def test_create_prompt_survives_malformed_body(client, body, admin_headers):
    res = client.post("/api/prompts/", json=body, headers=admin_headers)
    assert res.status_code != 500
    assert res.status_code == 400
    assert res.get_json()["error"] == "version_label et system_prompt_text requis."


@pytest.mark.parametrize("body", MALFORMED_BODIES)
def test_checkout_survives_malformed_body(client, body, monkeypatch, auth):
    # Checkout is disabled (503) without a Stripe key, which is the test
    # environment's default and already crash-proof. Set one so this test
    # actually exercises the request-body guard the fix added. Signed in, too:
    # checkout and verify are the owner's, and a signed-out caller is stopped
    # at 401 before either body is read.
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_dummy")
    res = client.post("/api/payments/checkout", json=body, headers=auth)
    assert res.status_code != 500
    assert res.status_code == 400
    assert res.get_json()["error"] == "analysis_id requis."


@pytest.mark.parametrize("body", MALFORMED_BODIES)
def test_verify_survives_malformed_body(client, body, monkeypatch, auth):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_dummy")
    res = client.post("/api/payments/verify", json=body, headers=auth)
    assert res.status_code != 500
    assert res.status_code == 400
    assert res.get_json()["error"] == "session_id requis."


# ── class B: a truthy non-string field must reach the route's own 400 ────────

@pytest.mark.parametrize("value", NON_STRING_VALUES)
def test_register_rejects_non_string_email(client, value):
    res = client.post("/api/auth/register", json={"email": value, "password": "longenough1"})
    assert res.status_code == 400
    assert res.get_json()["error"] == "Email et mot de passe requis."


@pytest.mark.parametrize("value", NON_STRING_VALUES)
def test_login_rejects_non_string_email(client, value):
    res = client.post("/api/auth/login", json={"email": value, "password": "x"})
    assert res.status_code == 401
    assert res.get_json()["error"] == "Identifiants incorrects."


@pytest.mark.parametrize("value", NON_STRING_VALUES)
def test_unlock_rejects_non_string_code(client, candidate, auth, value):
    a = _analysis(owner=candidate)
    res = client.post(f"/api/analyses/{a.id}/unlock", json={"code": value}, headers=auth)
    assert res.status_code == 400
    assert res.get_json()["error"] == "Code requis."


@pytest.mark.parametrize("value", NON_STRING_VALUES)
def test_price_feedback_rejects_non_string_bucket(client, candidate, auth, value):
    a = _analysis(owner=candidate)
    res = client.post(f"/api/analyses/{a.id}/price-feedback", json={"bucket": value}, headers=auth)
    assert res.status_code == 400
    assert res.get_json()["error"] == "Réponse invalide."


@pytest.mark.parametrize("value", NON_STRING_VALUES)
def test_create_counselor_code_rejects_non_string_label(client, value, admin_headers):
    res = client.post("/api/admin/counselor-codes", json={"label": value}, headers=admin_headers)
    assert res.status_code == 400
    assert res.get_json()["error"] == "label requis."


@pytest.mark.parametrize("value", NON_STRING_VALUES)
def test_create_prompt_rejects_non_string_version_label(client, value, admin_headers):
    res = client.post("/api/prompts/", json={
        "version_label": value, "system_prompt_text": "texte valide",
    }, headers=admin_headers)
    assert res.status_code == 400
    assert res.get_json()["error"] == "version_label et system_prompt_text requis."


@pytest.mark.parametrize("value", NON_STRING_VALUES)
def test_create_prompt_rejects_non_string_system_prompt_text(client, value, admin_headers):
    res = client.post("/api/prompts/", json={
        "version_label": "v-test", "system_prompt_text": value,
    }, headers=admin_headers)
    assert res.status_code == 400
    assert res.get_json()["error"] == "version_label et system_prompt_text requis."


# ── class C: a malformed PUT must never destroy a counselor's note ───────────

def test_malformed_put_never_wipes_an_existing_note(client):
    counselor = _approved_counselor("notes-guard@test.fr")
    headers = _headers(counselor)
    a = _analysis(door="advisor", counselor_id=counselor.id)
    url = f"/api/counselor/analyses/{a.id}/notes"

    def stored_body():
        # A fresh DB query, not the response body -- the whole point of the
        # regression is that the stored row survives.
        return CounselorNote.query.filter_by(analysis_id=a.id, counselor_id=counselor.id).first().body

    write = client.put(url, json={"note": "note clinique importante"}, headers=headers)
    assert write.status_code == 200
    assert write.get_json()["note"] == "note clinique importante"

    for refused in (
        {},                                  # no key at all
        {"autre": "x"},                      # the wrong key
        {"body": "x"},                       # the retired route's key
        {"note": None}, {"note": 5}, {"note": ["x"]}, {"note": {"a": "x"}},   # not a string
    ):
        res = client.put(url, json=refused, headers=headers)
        assert res.status_code == 400, refused
        assert res.get_json()["error"] == "Note invalide."
        assert stored_body() == "note clinique importante", refused

    for body in MALFORMED_BODIES:
        res = client.put(url, json=body, headers=headers)
        assert res.status_code == 400
        assert res.get_json()["error"] == "Note invalide."

    assert stored_body() == "note clinique importante"

    # An explicit {"note": ""} is a deliberate clear and must still work.
    cleared = client.put(url, json={"note": ""}, headers=headers)
    assert cleared.status_code == 200
    assert stored_body() == ""

    rewrite = client.put(url, json={"note": "note refaite"}, headers=headers)
    assert rewrite.status_code == 200
    assert stored_body() == "note refaite"

"""Profil de base — encryption boundary, bloc 5 semantics, OETH isolation."""

import pytest

from app.extensions import db as _db
from app.models.profile import (
    Profile,
    SensitiveProfile,
    normalize_conditions,
    prompt_context,
)
from app.models.user import User
from app.utils import crypto


@pytest.fixture
def profile(app):
    user = User(email="p@test.fr", password_hash="x")
    _db.session.add(user)
    _db.session.commit()
    p = Profile(user_id=user.id, prenom="Marie", nom="DUPONT")
    _db.session.add(p)
    _db.session.commit()
    return p


# ── encryption ───────────────────────────────────────────────────────────────

def test_round_trip(app):
    assert crypto.decrypt(crypto.encrypt("secret")) == "secret"
    assert crypto.decrypt_json(crypto.encrypt_json({"a": 1})) == {"a": 1}
    assert crypto.encrypt(None) is None
    assert crypto.decrypt(None) is None


def test_ciphertext_does_not_leak_plaintext(app):
    token = crypto.encrypt("travail de nuit")
    assert "travail" not in token
    assert "nuit" not in token


def test_bad_token_raises_rather_than_returning_garbage(app):
    with pytest.raises(crypto.DecryptionError):
        crypto.decrypt("not-a-fernet-token")


def test_columns_hold_ciphertext_not_plaintext(app, profile):
    s = SensitiveProfile(profile_id=profile.id)
    s.conditions = {"rythme": {"state": "a_eviter", "point_fort": False}}
    s.oeth = True
    _db.session.add(s)
    _db.session.commit()

    # Read the raw columns the way a DB export or log shipper would.
    row = _db.session.execute(
        _db.text("SELECT conditions_encrypted, oeth_encrypted FROM sensitive_profiles")
    ).first()
    assert "rythme" not in row[0]
    assert "a_eviter" not in row[0]
    assert row[1] not in ("true", "True", "1")

    # …but the model reads them back.
    assert s.conditions["rythme"]["state"] == "a_eviter"
    assert s.oeth is True


def test_oeth_defaults_false_when_never_set(app, profile):
    s = SensitiveProfile(profile_id=profile.id)
    _db.session.add(s)
    _db.session.commit()
    assert s.oeth is False
    assert s.conditions == {}


# ── the sensitive half never rides on the ordinary payload ───────────────────

def test_profile_to_dict_excludes_the_sensitive_half(app, profile):
    s = SensitiveProfile(profile_id=profile.id)
    s.conditions = {"environnement": {"state": "a_eviter", "point_fort": False}}
    s.oeth = True
    _db.session.add(s)
    _db.session.commit()

    payload = profile.to_dict()
    flat = str(payload).lower()
    assert "oeth" not in flat
    assert "environnement" not in flat
    assert "conditions" not in payload


def test_deleting_the_profile_removes_the_sensitive_row(app, profile):
    s = SensitiveProfile(profile_id=profile.id)
    s.oeth = True
    _db.session.add(s)
    _db.session.commit()

    _db.session.delete(profile)
    _db.session.commit()
    assert SensitiveProfile.query.count() == 0


# ── bloc 5 validation ────────────────────────────────────────────────────────

def test_normalize_drops_unknown_families_and_states():
    raw = {
        "rythme": {"state": "a_eviter", "point_fort": True},
        "teleportation": {"state": "a_eviter"},          # not a family
        "attention": {"state": "parfois"},               # not a state
        "relation": "me_convient",                       # not a mapping
    }
    out = normalize_conditions(raw)
    assert set(out) == {"rythme"}
    assert out["rythme"] == {"state": "a_eviter", "point_fort": True}


def test_normalize_tolerates_junk():
    assert normalize_conditions(None) == {}
    assert normalize_conditions("nope") == {}
    assert normalize_conditions({}) == {}


# ── the rule that makes bloc 5 worth collecting ──────────────────────────────

def test_me_convient_is_never_a_strength():
    """Parcours doc: tolerating a demanding requirement differentiates you;
    merely preferring something does not."""
    ctx = prompt_context({
        "environnement": {"state": "me_convient", "point_fort": False},
    })
    assert ctx["points_forts"] == []


def test_point_fort_on_a_demanding_requirement_is_a_strength():
    ctx = prompt_context({
        "rythme": {"state": "me_convient", "point_fort": True},
        "effort_physique": {"state": "me_convient", "point_fort": True},
    })
    assert ctx["points_forts"] == ["effort_physique", "rythme"]


def test_point_fort_on_a_soft_preference_is_not_promoted():
    ctx = prompt_context({
        "consignes": {"state": "me_convient", "point_fort": True},
    })
    assert ctx["points_forts"] == []


def test_adaptations_and_avoidances_are_reported_separately():
    ctx = prompt_context({
        "attention": {"state": "possible_avec_adaptation", "point_fort": False},
        "deplacements": {"state": "a_eviter", "point_fort": False},
    })
    assert ctx["possible_avec_adaptation"] == ["attention"]
    assert ctx["a_eviter"] == ["deplacements"]
    assert ctx["points_forts"] == []


# ── routes ───────────────────────────────────────────────────────────────────

@pytest.fixture
def auth(app):
    """A logged-in candidate, as Bearer headers (TestingConfig uses headers)."""
    from flask_jwt_extended import create_access_token
    user = User(email="route@test.fr", password_hash="x")
    _db.session.add(user)
    _db.session.commit()
    token = create_access_token(identity=str(user.id), additional_claims={"role": "candidate"})
    return {"Authorization": f"Bearer {token}"}


BASE = {
    "consent": True,
    "prenom": "Marie", "nom": "dupont",
    "ville": "Lyon", "rayon": "30km", "tranche_age": "35_44",
    "situation": "en_recherche",
}


def test_create_requires_consent(client, auth):
    res = client.put("/api/profile", json={**BASE, "consent": False}, headers=auth)
    assert res.status_code == 400
    assert "consentement" in res.get_json()["errors"][0].lower()


def test_create_and_read_back(client, auth):
    res = client.put("/api/profile", json=BASE, headers=auth)
    assert res.status_code == 201
    assert res.get_json()["profile"]["nom"] == "DUPONT"  # displayed in caps

    got = client.get("/api/profile", headers=auth).get_json()["profile"]
    assert got["ville"] == "Lyon"
    assert got["consent_at"] is not None


def test_rejects_unknown_enum_values(client, auth):
    res = client.put("/api/profile", json={**BASE, "rayon": "la_galaxie"}, headers=auth)
    assert res.status_code == 400


def test_reconversion_scope_requires_a_reconversion(client, auth):
    res = client.put(
        "/api/profile",
        json={**BASE, "situation": "en_recherche", "reconversion_scope": "changer_de_metier"},
        headers=auth,
    )
    assert res.status_code == 400


def test_changing_away_from_reconversion_clears_the_scope(client, auth):
    client.put("/api/profile", json={
        **BASE, "situation": "en_reconversion", "reconversion_scope": "changer_de_metier",
    }, headers=auth)
    res = client.put("/api/profile", json={**BASE, "situation": "en_poste_evolution"}, headers=auth)
    assert res.get_json()["profile"]["reconversion_scope"] is None


def test_bloc5_is_stored_and_returned_on_its_own_endpoint(client, auth):
    client.put("/api/profile", json={
        **BASE,
        "conditions": {"rythme": {"state": "a_eviter", "point_fort": False}},
    }, headers=auth)

    # not on the ordinary payload …
    assert "conditions" not in client.get("/api/profile", headers=auth).get_json()["profile"]
    # … but reachable explicitly
    conditions = client.get("/api/profile/conditions", headers=auth).get_json()["conditions"]
    assert conditions["rythme"]["state"] == "a_eviter"


def test_deleting_the_profile_is_a_full_erasure(client, auth):
    client.put("/api/profile", json={**BASE, "oeth": True}, headers=auth)
    assert client.delete("/api/profile", headers=auth).status_code == 200
    assert client.get("/api/profile", headers=auth).get_json()["profile"] is None
    assert SensitiveProfile.query.count() == 0


# ── the OETH invariant ───────────────────────────────────────────────────────

def _signup(client, email):
    from flask_jwt_extended import create_access_token
    user = User(email=email, password_hash="x")
    _db.session.add(user)
    _db.session.commit()
    token = create_access_token(identity=str(user.id), additional_claims={"role": "candidate"})
    return {"Authorization": f"Bearer {token}"}


def test_oeth_is_indistinguishable_from_the_outside(client, app):
    """CDC §3.1 / Parcours bloc 6: ticking the box must trigger nothing
    visible. If any response differs, the person learns they just flagged
    themselves and the equal-treatment promise collapses."""
    a = _signup(client, "oeth-yes@test.fr")
    b = _signup(client, "oeth-no@test.fr")

    res_a = client.put("/api/profile", json={**BASE, "oeth": True}, headers=a)
    res_b = client.put("/api/profile", json={**BASE, "oeth": False}, headers=b)

    assert res_a.status_code == res_b.status_code

    def scrub(payload):
        p = dict(payload["profile"])
        for volatile in ("id", "created_at", "updated_at", "consent_at"):
            p.pop(volatile, None)
        return p

    assert scrub(res_a.get_json()) == scrub(res_b.get_json())
    assert scrub(client.get("/api/profile", headers=a).get_json()) == \
           scrub(client.get("/api/profile", headers=b).get_json())


def test_owner_gets_their_own_oeth_answer_back(client, app):
    """The invariant is "no visible reaction", not "no persistence". Dropping
    the stored answer would silently clear a status governing the person's
    rights on their next save."""
    a = _signup(client, "oeth-persist@test.fr")
    client.put("/api/profile", json={**BASE, "oeth": True}, headers=a)
    assert client.get("/api/profile/conditions", headers=a).get_json()["oeth"] is True


def test_oeth_never_rides_on_the_ordinary_profile_payload(client, app):
    """It travels only on the sensitive endpoint, so it cannot reach an admin
    view, a log line, or a PDF by accident."""
    a = _signup(client, "oeth-channel@test.fr")
    client.put("/api/profile", json={**BASE, "oeth": True}, headers=a)
    body = client.get("/api/profile", headers=a).get_data(as_text=True)
    assert "oeth" not in body.lower()


def test_the_sensitive_row_exists_either_way(client, app):
    """Row presence must not encode the flag: if the row only existed for
    people who ticked the box, anything that can read the table learns who
    they are without decrypting anything."""
    a = _signup(client, "row-yes@test.fr")
    b = _signup(client, "row-no@test.fr")
    client.put("/api/profile", json={**BASE, "oeth": True}, headers=a)
    client.put("/api/profile", json={**BASE, "oeth": False}, headers=b)
    assert SensitiveProfile.query.count() == 2

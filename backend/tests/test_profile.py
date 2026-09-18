"""Profil de base — encryption boundary, bloc 5 semantics, OETH isolation."""

import pytest

from app.extensions import db as _db
from app.models.profile import (
    ACCEPTED_AGE_BRACKETS,
    AGE_BRACKETS,
    APPETENCE_ETUDES,
    DIPLOMES,
    TYPES_ETUDES,
    Profile,
    SensitiveProfile,
    normalize_conditions,
    prompt_context,
)
from app.models.user import User
from app.routes.profile import CONSENT_SENSITIVE_VERSION
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


# ── age brackets ─────────────────────────────────────────────────────────────

def test_youth_brackets_are_accepted(client, auth):
    """The voyage brought school-age candidates in; "moins_25" was one bucket
    where the youth schemes need three."""
    for bracket in ("14_17", "18_21", "22_24"):
        res = client.put("/api/profile", json={**BASE, "tranche_age": bracket}, headers=auth)
        assert res.status_code in (200, 201), bracket
        assert res.get_json()["profile"]["tranche_age"] == bracket


def test_brackets_meet_at_25_without_overlapping(app):
    """22_24 stops exactly where 25_34 starts. A 25-year-old has one bucket,
    not two, and no row written under the five-bracket set changes meaning."""
    assert "22_25" not in AGE_BRACKETS
    assert AGE_BRACKETS.index("22_24") + 1 == AGE_BRACKETS.index("25_34")
    for bracket in ("25_34", "35_44", "45_54", "55_plus"):
        assert bracket in AGE_BRACKETS


# ── « Ton parcours » ─────────────────────────────────────────────────────────

def test_parcours_block_round_trips(client, auth):
    """The four questions asked after S1. appetence_etudes is the one that
    filters the pistes by study length, so it earns its own assertion."""
    res = client.put("/api/profile", json={
        **BASE,
        "diplome": "bac",
        "type_etudes": "technologiques",
        "intitule_etudes": "Bac STI2D",
        "appetence_etudes": "courtes",
    }, headers=auth)
    assert res.status_code in (200, 201)

    got = client.get("/api/profile", headers=auth).get_json()["profile"]
    assert got["diplome"] == "bac"
    assert got["type_etudes"] == "technologiques"
    assert got["intitule_etudes"] == "Bac STI2D"
    assert got["appetence_etudes"] == "courtes"


def test_every_parcours_option_is_accepted(client, auth):
    for field, allowed in (
        ("diplome", DIPLOMES),
        ("type_etudes", TYPES_ETUDES),
        ("appetence_etudes", APPETENCE_ETUDES),
    ):
        for value in allowed:
            res = client.put("/api/profile", json={**BASE, field: value}, headers=auth)
            assert res.status_code in (200, 201), f"{field}={value}"
            assert res.get_json()["profile"][field] == value


def test_parcours_rejects_an_unknown_option(client, auth):
    for field in ("diplome", "type_etudes", "appetence_etudes"):
        res = client.put("/api/profile", json={**BASE, field: "doctorat_honoris"}, headers=auth)
        assert res.status_code == 400, field


def test_parcours_is_optional(client, auth):
    """A profile saved before this block existed must still save."""
    res = client.put("/api/profile", json=BASE, headers=auth)
    assert res.status_code in (200, 201)
    got = client.get("/api/profile", headers=auth).get_json()["profile"]
    assert got["diplome"] is None
    assert got["appetence_etudes"] is None


def test_intitule_etudes_is_free_text_and_clearable(client, auth):
    client.put("/api/profile", json={**BASE, "intitule_etudes": "CAP Cuisine"}, headers=auth)
    res = client.put("/api/profile", json={**BASE, "intitule_etudes": ""}, headers=auth)
    assert res.get_json()["profile"]["intitule_etudes"] is None


def test_legacy_bracket_is_accepted_but_never_offered(client, auth):
    """Someone who answered before the split edits another field. The bracket
    they never touched must not reject the write — and the form re-asks."""
    assert "moins_25" not in AGE_BRACKETS
    assert "moins_25" in ACCEPTED_AGE_BRACKETS
    res = client.put("/api/profile", json={**BASE, "tranche_age": "moins_25"}, headers=auth)
    assert res.status_code in (200, 201)


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
        "consent_sensitive": True,
        "conditions": {"rythme": {"state": "a_eviter", "point_fort": False}},
    }, headers=auth)

    # not on the ordinary payload …
    assert "conditions" not in client.get("/api/profile", headers=auth).get_json()["profile"]
    # … but reachable explicitly
    conditions = client.get("/api/profile/conditions", headers=auth).get_json()["conditions"]
    assert conditions["rythme"]["state"] == "a_eviter"


def test_deleting_the_profile_is_a_full_erasure(client, auth):
    client.put("/api/profile", json={**BASE, "consent_sensitive": True, "oeth": True},
               headers=auth)
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

    res_a = client.put("/api/profile", json={**BASE, "consent_sensitive": True, "oeth": True}, headers=a)
    res_b = client.put("/api/profile", json={**BASE, "consent_sensitive": True, "oeth": False}, headers=b)

    assert res_a.status_code == res_b.status_code

    def scrub(payload):
        p = dict(payload["profile"])
        for volatile in ("id", "created_at", "updated_at", "consent_at",
                         "consent_sensitive_at"):
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
    client.put("/api/profile", json={**BASE, "consent_sensitive": True, "oeth": True}, headers=a)
    assert client.get("/api/profile/conditions", headers=a).get_json()["oeth"] is True


def test_oeth_never_rides_on_the_ordinary_profile_payload(client, app):
    """It travels only on the sensitive endpoint, so it cannot reach an admin
    view, a log line, or a PDF by accident."""
    a = _signup(client, "oeth-channel@test.fr")
    client.put("/api/profile", json={**BASE, "consent_sensitive": True, "oeth": True}, headers=a)
    body = client.get("/api/profile", headers=a).get_data(as_text=True)
    assert "oeth" not in body.lower()


def test_the_sensitive_row_exists_either_way(client, app):
    """Row presence must not encode the flag: if the row only existed for
    people who ticked the box, anything that can read the table learns who
    they are without decrypting anything."""
    a = _signup(client, "row-yes@test.fr")
    b = _signup(client, "row-no@test.fr")
    client.put("/api/profile", json={**BASE, "consent_sensitive": True, "oeth": True}, headers=a)
    client.put("/api/profile", json={**BASE, "consent_sensitive": True, "oeth": False}, headers=b)
    assert SensitiveProfile.query.count() == 2


# ── the consent bloc 5 needs of its own ──────────────────────────────────────

def test_bloc5_refuses_to_store_without_its_own_consent(client, auth):
    """The signup CGV covers the ordinary half. Bloc 5 is health-adjacent and
    OETH is a disability status — Art. 9 — so a generic tick taken before the
    person had seen the product is not consent for either."""
    res = client.put("/api/profile", json={
        **BASE, "conditions": {"rythme": {"state": "a_eviter", "point_fort": False}},
    }, headers=auth)
    assert res.status_code == 400
    assert "conditions de travail" in res.get_json()["errors"][0]

    # and nothing was written on the way out
    assert client.get("/api/profile/conditions", headers=auth).get_json()["conditions"] == {}


def test_bloc5_consent_is_recorded_once_and_then_carries(client, auth):
    res = client.put("/api/profile", json={
        **BASE, "consent_sensitive": True,
        "conditions": {"rythme": {"state": "a_eviter", "point_fort": False}},
    }, headers=auth)
    assert res.status_code in (200, 201)

    first = res.get_json()["profile"]["consent_sensitive_at"]
    assert first is not None
    assert res.get_json()["profile"]["consent_sensitive_version"] == CONSENT_SENSITIVE_VERSION

    # a later edit needs no second tick, and does not move the record
    again = client.put("/api/profile", json={
        **BASE, "conditions": {"attention": {"state": "me_convient", "point_fort": False}},
    }, headers=auth)
    assert again.status_code == 200
    assert again.get_json()["profile"]["consent_sensitive_at"] == first


def test_the_consent_gate_does_not_leak_the_oeth_flag(client, app):
    """The gate keys on the presence of the sensitive fields, never on their
    values. Were it to refuse `oeth: true` and accept `oeth: false`, the
    refusal itself would tell the person they had just flagged themselves."""
    a = _signup(client, "gate-yes@test.fr")
    b = _signup(client, "gate-no@test.fr")

    res_a = client.put("/api/profile", json={**BASE, "oeth": True}, headers=a)
    res_b = client.put("/api/profile", json={**BASE, "oeth": False}, headers=b)

    assert res_a.status_code == res_b.status_code == 400
    assert res_a.get_json() == res_b.get_json()


def test_a_profile_without_bloc5_never_needs_the_second_consent(client, auth):
    """Most people never open the conditions step. Saving the ordinary half
    must not demand a consent for data they did not give."""
    res = client.put("/api/profile", json=BASE, headers=auth)
    assert res.status_code in (200, 201)
    assert res.get_json()["profile"]["consent_sensitive_at"] is None


def test_conditions_seen_tracks_the_step_not_the_answers(client, auth):
    """The hub mirrors session_lock from the ordinary payload, so it needs to
    know the step was played. An empty bloc 5 is a complete answer."""
    assert client.put("/api/profile", json=BASE, headers=auth) \
        .get_json()["profile"]["conditions_seen"] is False

    res = client.put("/api/profile", json={**BASE, "consent_sensitive": True,
                                           "conditions": {}}, headers=auth)
    assert res.get_json()["profile"]["conditions_seen"] is True


def test_conditions_seen_grandfathers_a_row_written_before_the_consent(app, profile):
    """Answers written through /profil before the second consent existed are
    taken at their word rather than sent back through a step already answered."""
    s = SensitiveProfile(profile_id=profile.id)
    s.conditions = {"attention": {"state": "a_eviter", "point_fort": False}}
    _db.session.add(s)
    _db.session.commit()

    assert profile.consent_sensitive_at is None
    assert profile.conditions_seen is True

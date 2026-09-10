"""Le voyage — what the model guarantees and what the API will and won't do.

Model and routes live in one file, the way test_profile.py keeps bloc 5's
encryption, its validation and its endpoints together: each guarantee only
means something end to end — a route writes, the column holds ciphertext, and
the payload never carries it back.
"""
from datetime import datetime

import pytest

from app.extensions import db as _db
from app.models.user import User
from app.models.profile import Profile
from app.models.voyage import (
    CONSENT_VERSION,
    LOCK_CODE,
    LOCK_ORDER,
    LOCK_PROFILE,
    PORTRAIT_KEYS,
    STATUS_EN_COURS,
    STATUS_S0,
    STATUS_TERMINE,
    Voyage,
    VoyageNote,
    session_lock,
)
from app.services.voyage import bank
from app.utils import crypto


# ── helpers, used by every task in this file ─────────────────────────────────

def _user(email, role="candidate"):
    user = User(email=email, password_hash="x", role=role)
    _db.session.add(user)
    _db.session.commit()
    return user


def _headers(user):
    """Bearer headers — TestingConfig reads the JWT from headers, not cookies."""
    from flask_jwt_extended import create_access_token
    token = create_access_token(identity=str(user.id), additional_claims={"role": user.role})
    return {"Authorization": f"Bearer {token}"}


def _voyage(user, **overrides):
    """A row with the fields POST /api/voyage always sets, plus overrides."""
    fields = {
        "user_id": user.id,
        "status": STATUS_EN_COURS,
        "sessions_completed": [],
        "consent_at": datetime.utcnow(),
        "consent_version": CONSENT_VERSION,
        "age_attested": True,
    }
    fields.update(overrides)
    voyage = Voyage(**fields)
    _db.session.add(voyage)
    _db.session.commit()
    return voyage


def _answers_for(n):
    """One valid answer per item of session n: True for the S0 checklist, the
    first option letter for a scene."""
    return {
        item["id"]: True if n == "0" else item["options"][0]["letter"]
        for item in bank.items(n)
    }


@pytest.fixture
def candidate(app):
    return _user("voyageur@test.fr")


@pytest.fixture
def auth(candidate):
    return _headers(candidate)


# ── the encrypted payloads ───────────────────────────────────────────────────

def test_a_new_voyage_starts_empty_and_silent(app, candidate):
    voyage = _voyage(candidate)
    assert voyage.status == STATUS_EN_COURS
    assert voyage.responses == {"answers": {}, "billets": {}}
    assert voyage.micro == {}
    assert voyage.portrait == {}
    assert voyage.micro_status == "none"
    assert voyage.portrait_status == "none"
    assert voyage.micro_phrase is None
    assert voyage.portrait_sections == {}
    assert voyage.has_code is False
    assert voyage.is_open is True


def test_responses_round_trip_through_the_property(app, candidate):
    voyage = _voyage(candidate)
    voyage.responses = {"answers": {"S0-01": True, "S1-1": "A"},
                        "billets": {"0": {"surprise": "je déteste le bureau"}}}
    _db.session.commit()

    stored = Voyage.query.get(voyage.id).responses
    assert stored["answers"] == {"S0-01": True, "S1-1": "A"}
    assert stored["billets"]["0"]["surprise"] == "je déteste le bureau"


def test_both_response_keys_always_exist(app, candidate):
    """Scoring reads responses["answers"] without a guard — the model owes it
    the shape whatever was stored."""
    voyage = _voyage(candidate)
    voyage.responses = {"answers": {"S0-01": True}}
    _db.session.commit()
    assert Voyage.query.get(voyage.id).responses["billets"] == {}


def test_columns_hold_ciphertext_not_plaintext(app, candidate):
    """The guarantee that makes a psychometric read-out storable at all: a DB
    export, an admin query or a log shipper sees nothing."""
    voyage = _voyage(candidate)
    voyage.responses = {"answers": {"S0-01": True},
                        "billets": {"0": {"surprise": "je déteste le bureau"}}}
    voyage.micro = {"phrase": "Tu cherches des endroits où ce que tu fabriques sert."}
    _db.session.commit()

    row = _db.session.execute(_db.text(
        "SELECT responses_encrypted, micro_encrypted FROM voyages"
    )).first()
    assert "S0-01" not in row[0]
    assert "bureau" not in row[0]
    assert "endroits" not in row[1]


def test_an_unreadable_payload_raises_rather_than_reading_as_empty(app, candidate):
    """Precedent: test_profile.py:41-43. A silently swallowed DecryptionError
    would make a key-rotation incident look like "never answered" — every
    voyage reads as empty, session_complete goes False everywhere, and no
    test fails."""
    voyage = _voyage(candidate)
    for column in ("responses_encrypted", "micro_encrypted", "portrait_encrypted"):
        setattr(voyage, column, "not-a-fernet-token")
    for prop in ("responses", "micro", "portrait"):
        with pytest.raises(crypto.DecryptionError):
            getattr(voyage, prop)


def test_portrait_sections_needs_all_six_keys(app, candidate):
    voyage = _voyage(candidate)
    voyage.portrait = {"sections": {"accroche": "une phrase"}}
    _db.session.commit()
    assert voyage.portrait_sections == {}

    voyage.portrait = {"sections": {k: f"texte {k}" for k in PORTRAIT_KEYS}}
    _db.session.commit()
    assert voyage.portrait_sections == {k: f"texte {k}" for k in PORTRAIT_KEYS}


# ── scoring ──────────────────────────────────────────────────────────────────

def test_synthesis_reads_the_answers_the_model_stores(app, candidate):
    """The bug this catches: passing responses["answers"] instead of responses
    to scoring.synthesize — every score would then read as None/False without
    the suite noticing, because nothing else exercises synthesis()."""
    voyage = _voyage(candidate)
    voyage.responses = {"answers": _answers_for("0"), "billets": {}}
    _db.session.commit()

    sheet = voyage.synthesis()
    assert set(sheet) == {"completeness", "riasec", "s0", "s2", "s3",
                          "s4", "s5", "scoring_version"}
    assert sheet["completeness"]["0"] is True
    assert sheet["completeness"]["1"] is False
    assert sheet["scoring_version"] == bank.SCORING_VERSION
    assert sheet["s0"] is not None and sheet["riasec"] is None


# ── to_dict: the only thing a candidate ever sees of the row ─────────────────

TO_DICT_KEYS = {
    "id", "status", "sessions_completed", "consent_at", "age_attested",
    "has_code", "micro_status", "micro_phrase", "portrait_status",
    "share_token", "created_at", "completed_at",
}


def test_to_dict_carries_exactly_twelve_keys(app, candidate):
    voyage = _voyage(candidate)
    voyage.responses = {"answers": {"S0-01": True}, "billets": {}}
    voyage.portrait = {"sections": {k: "x" for k in PORTRAIT_KEYS}, "snapshot": {"s0": {}},
                       "flags": ["vocabulaire"], "edited": True}
    _db.session.commit()

    payload = voyage.to_dict()
    assert set(payload) == TO_DICT_KEYS
    flat = str(payload)
    for forbidden in ("S0-01", "snapshot", "vocabulaire", "edited", "user_id"):
        assert forbidden not in flat


def test_to_dict_survives_an_unflushed_row(app, candidate):
    """created_at's default is Python-side, applied at flush — a caller that
    serialises before commit() must not get an AttributeError on None."""
    voyage = Voyage(
        user_id=candidate.id,
        status=STATUS_EN_COURS,
        sessions_completed=[],
        consent_at=datetime.utcnow(),
        consent_version=CONSENT_VERSION,
        age_attested=True,
    )
    payload = voyage.to_dict()
    assert payload["created_at"] is None
    assert set(payload) == TO_DICT_KEYS


def test_the_phrase_is_the_one_derived_thing_a_candidate_may_see(app, candidate):
    voyage = _voyage(candidate)
    voyage.micro = {"phrase": "Tu avances mieux quand le résultat se voit.",
                    "prompt_version_id": "pv-1", "tokens_in": 40, "tokens_out": 20}
    voyage.micro_status = "success"
    _db.session.commit()
    payload = voyage.to_dict()
    assert payload["micro_phrase"] == "Tu avances mieux quand le résultat se voit."
    assert "prompt_version_id" not in payload
    assert "tokens_in" not in payload


def test_share_token_stays_hidden_until_the_voyage_is_finished(app, candidate):
    voyage = _voyage(candidate, status=STATUS_S0, share_token="tok-early")
    assert voyage.to_dict()["share_token"] is None

    voyage.status = STATUS_TERMINE
    _db.session.commit()
    assert voyage.to_dict()["share_token"] == "tok-early"


# ── lookups ──────────────────────────────────────────────────────────────────

def test_open_current_and_latest(app, candidate):
    finished = _voyage(candidate, status=STATUS_TERMINE)
    assert Voyage.open_for(candidate.id) is None
    assert Voyage.current_for(candidate.id).id == finished.id

    open_one = _voyage(candidate, status=STATUS_S0)
    assert Voyage.open_for(candidate.id).id == open_one.id
    assert Voyage.current_for(candidate.id).id == open_one.id
    assert Voyage.latest_for(candidate.id).id == open_one.id


def test_lookups_are_none_for_a_user_who_never_played(app, candidate):
    assert Voyage.current_for(candidate.id) is None
    assert Voyage.latest_for(None) is None
    assert Voyage.by_token("") is None
    assert Voyage.by_token("unknown") is None
    assert Voyage.for_prompt(None) is None


def test_for_prompt_prefers_a_validated_portrait_then_a_phrase(app, candidate):
    """Spec § Injection: before validation an analysis must not tell the person
    what the counselor has not restituted yet — but S0's phrase may travel."""
    assert Voyage.for_prompt(candidate.id) is None

    with_phrase = _voyage(candidate, status=STATUS_S0, micro_status="success")
    assert Voyage.for_prompt(candidate.id).id == with_phrase.id

    validated = _voyage(candidate, status=STATUS_TERMINE,
                        micro_status="success", portrait_status="validated")
    assert Voyage.for_prompt(candidate.id).id == validated.id


def test_a_draft_portrait_is_not_enough_for_for_prompt(app, candidate):
    _voyage(candidate, status=STATUS_TERMINE, portrait_status="draft")
    assert Voyage.for_prompt(candidate.id) is None


# ── notes ────────────────────────────────────────────────────────────────────

def test_deleting_a_voyage_erases_its_notes(app, candidate):
    counselor = _user("note-cascade@test.fr", role="counselor")
    voyage = _voyage(candidate)
    _db.session.add(VoyageNote(voyage_id=voyage.id, counselor_id=counselor.id, body="vu"))
    _db.session.commit()

    _db.session.delete(voyage)
    _db.session.commit()
    assert VoyageNote.query.count() == 0


def test_note_to_dict_has_four_keys(app, candidate):
    counselor = _user("note-shape@test.fr", role="counselor")
    voyage = _voyage(candidate)
    note = VoyageNote(voyage_id=voyage.id, counselor_id=counselor.id, body="à revoir")
    _db.session.add(note)
    _db.session.commit()
    assert set(note.to_dict()) == {"id", "voyage_id", "body", "updated_at"}
    assert note.to_dict()["body"] == "à revoir"


# ── the session gate ─────────────────────────────────────────────────────────

def _profile_for(user, **fields):
    profile = Profile(user_id=user.id, **fields)
    _db.session.add(profile)
    _db.session.commit()
    return profile


def test_session_zero_is_open_as_soon_as_the_voyage_exists(app, candidate):
    """S0 is the 5-minute self-serve half: no code, no profile, no counselor."""
    assert session_lock(_voyage(candidate), None, "0") is None


def test_no_voyage_locks_everything(app):
    assert session_lock(None, None, "0") == LOCK_ORDER
    assert session_lock(None, None, "1") == LOCK_ORDER


def test_the_later_sessions_need_a_counselor_code(app, candidate):
    voyage = _voyage(candidate, sessions_completed=["0"])
    assert session_lock(voyage, None, "1") == LOCK_CODE


def test_the_later_sessions_need_a_prenom_and_an_age_bracket(app, candidate):
    """The portrait uses both; « une information, une seule fois » forbids
    asking again inside the voyage."""
    voyage = _voyage(candidate, sessions_completed=["0"], counselor_code_id="code-1")
    assert session_lock(voyage, None, "1") == LOCK_PROFILE
    profile = _profile_for(candidate, prenom="Marie")
    assert session_lock(voyage, profile, "1") == LOCK_PROFILE
    profile.tranche_age = "25_34"
    _db.session.commit()
    assert session_lock(voyage, profile, "1") is None


def test_sessions_come_in_order(app, candidate):
    voyage = _voyage(candidate, sessions_completed=["0"], counselor_code_id="code-1")
    profile = _profile_for(candidate, prenom="Marie", tranche_age="25_34")
    assert session_lock(voyage, profile, "2") == LOCK_ORDER
    voyage.sessions_completed = ["0", "1"]
    _db.session.commit()
    assert session_lock(voyage, profile, "2") is None


def test_the_first_failing_rule_wins(app, candidate):
    """No code *and* no profile *and* out of order still reads « Avec un
    conseiller » — the one the person can actually act on first."""
    voyage = _voyage(candidate)
    assert session_lock(voyage, None, "5") == LOCK_CODE


# ── GET /api/voyage/bank ─────────────────────────────────────────────────────

WEIGHT_KEYS = {"riasec", "axes", "sdt", "schwartz", "big5", "style", "env",
               "risk", "sens", "plain"}


def _walk(node):
    """Every dict in a nested JSON payload."""
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def test_the_bank_serves_text_and_no_weights(client, auth):
    """Decision 6: the option→trait mapping is the product and the counselor
    manual is marked confidential. It never leaves the server."""
    res = client.get("/api/voyage/bank", headers=auth)
    assert res.status_code == 200
    payload = res.get_json()["bank"]
    assert payload["scoring_version"] == bank.SCORING_VERSION
    assert [s["n"] for s in payload["sessions"]] == list(bank.SESSION_IDS)
    for node in _walk(payload):
        leaked = WEIGHT_KEYS & set(node)
        assert not leaked, f"scoring key(s) {leaked} reached the client"


def test_the_bank_needs_an_account(client):
    assert client.get("/api/voyage/bank").status_code == 401


# ── GET / POST /api/voyage ───────────────────────────────────────────────────

def test_a_user_who_never_played_has_no_voyage(client, auth):
    res = client.get("/api/voyage", headers=auth)
    assert res.status_code == 200
    assert res.get_json()["voyage"] is None


def test_creation_requires_consent_and_the_age_attestation(client, auth):
    """Decision 13: psychometric data needs its own consent record, and 15 is
    the French digital-consent age."""
    res = client.post("/api/voyage", json={}, headers=auth)
    assert res.status_code == 400
    errors = res.get_json()["errors"]
    assert "Le consentement est requis." in errors
    assert "Vous devez attester avoir 15 ans ou plus." in errors

    res = client.post("/api/voyage", json={"consent": True, "age_attested": False}, headers=auth)
    assert res.status_code == 400
    assert res.get_json()["errors"] == ["Vous devez attester avoir 15 ans ou plus."]

    assert Voyage.query.count() == 0


def test_creation_stamps_the_consent_and_the_scoring_version(client, auth):
    res = client.post("/api/voyage", json={"consent": True, "age_attested": True}, headers=auth)
    assert res.status_code == 201
    payload = res.get_json()["voyage"]
    assert payload["status"] == STATUS_EN_COURS
    assert payload["sessions_completed"] == []
    assert payload["consent_at"] is not None
    assert payload["age_attested"] is True

    row = Voyage.query.one()
    assert row.consent_version == CONSENT_VERSION
    assert row.scoring_version == bank.SCORING_VERSION


def test_only_one_open_voyage_at_a_time(client, auth):
    client.post("/api/voyage", json={"consent": True, "age_attested": True}, headers=auth)
    res = client.post("/api/voyage", json={"consent": True, "age_attested": True}, headers=auth)
    assert res.status_code == 409
    assert res.get_json()["error"] == "Un voyage est déjà en cours."
    assert Voyage.query.count() == 1


def test_a_retake_is_allowed_once_the_previous_one_is_finished(client, auth, candidate):
    """Decision 3: the old row is kept, because analyses reference it."""
    _voyage(candidate, status=STATUS_TERMINE, share_token="tok-old")
    res = client.post("/api/voyage", json={"consent": True, "age_attested": True}, headers=auth)
    assert res.status_code == 201
    assert Voyage.query.count() == 2


def test_a_voyage_is_only_ever_the_callers_own(client, auth, candidate):
    """No candidate endpoint takes an id from the client, so there is nothing
    to enumerate — but the neighbour must still see their own state."""
    _voyage(candidate, status=STATUS_S0)
    neighbour = _headers(_user("voisin@test.fr"))
    assert client.get("/api/voyage", headers=neighbour).get_json()["voyage"] is None


# ── DELETE /api/voyage ───────────────────────────────────────────────────────

def test_erasure_is_independent_of_the_profile(client, auth, candidate):
    """Decision 14 — the two-speed argument to a prescriber: « vous gardez le
    contrôle de ce qu'on garde »."""
    _db.session.add(Profile(user_id=candidate.id, prenom="Marie", tranche_age="25_34"))
    _db.session.commit()
    client.post("/api/voyage", json={"consent": True, "age_attested": True}, headers=auth)

    res = client.delete("/api/voyage", headers=auth)
    assert res.status_code == 200
    assert res.get_json()["message"] == "Voyage supprimé."
    assert Voyage.query.count() == 0
    assert Profile.query.filter_by(user_id=candidate.id).count() == 1


def test_erasing_nothing_is_not_an_error(client, auth):
    """Mirrors DELETE /api/profile: the person asked for nothing to be left,
    and nothing is left."""
    res = client.delete("/api/voyage", headers=auth)
    assert res.status_code == 200
    assert res.get_json()["message"] == "Aucun voyage à supprimer."

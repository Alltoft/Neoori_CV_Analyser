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


def test_portrait_sections_needs_all_six_keys(app, candidate):
    voyage = _voyage(candidate)
    voyage.portrait = {"sections": {"accroche": "une phrase"}}
    _db.session.commit()
    assert voyage.portrait_sections == {}

    voyage.portrait = {"sections": {k: f"texte {k}" for k in PORTRAIT_KEYS}}
    _db.session.commit()
    assert set(voyage.portrait_sections) == set(PORTRAIT_KEYS)


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

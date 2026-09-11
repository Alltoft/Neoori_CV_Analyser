"""Le voyage — what the model guarantees and what the API will and won't do.

Model and routes live in one file, the way test_profile.py keeps bloc 5's
encryption, its validation and its endpoints together: each guarantee only
means something end to end — a route writes, the column holds ciphertext, and
the payload never carries it back.
"""
from datetime import datetime, timedelta

import pytest

from app.extensions import db as _db
from app.models.analysis import Analysis
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
    voyage = _voyage(candidate, sessions_completed=["0"], counselor_code_id=_code().id)
    assert session_lock(voyage, None, "1") == LOCK_PROFILE
    profile = _profile_for(candidate, prenom="Marie")
    assert session_lock(voyage, profile, "1") == LOCK_PROFILE
    profile.tranche_age = "25_34"
    _db.session.commit()
    assert session_lock(voyage, profile, "1") is None


def test_sessions_come_in_order(app, candidate):
    voyage = _voyage(candidate, sessions_completed=["0"], counselor_code_id=_code().id)
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
    to enumerate — but each caller must see their own row and never the
    other's. Both users have a voyage, so this fails if the ownership filter
    is ever dropped (a "most recent row" bug would pass the earlier version
    of this test but not this one)."""
    voyage_a = _voyage(candidate, status=STATUS_S0)
    neighbour_user = _user("voisin@test.fr")
    voyage_b = _voyage(neighbour_user, status=STATUS_S0)
    neighbour = _headers(neighbour_user)
    assert client.get("/api/voyage", headers=neighbour).get_json()["voyage"]["id"] == voyage_b.id
    assert client.get("/api/voyage", headers=auth).get_json()["voyage"]["id"] == voyage_a.id


def test_creation_rejects_a_json_array_body(client, auth):
    """A JSON array is valid, truthy JSON — it must not survive past the
    dict check and crash data.get() into an unhandled 500."""
    res = client.post("/api/voyage", json=[1, 2, 3], headers=auth)
    assert res.status_code == 400
    errors = res.get_json()["errors"]
    assert "Le consentement est requis." in errors
    assert "Vous devez attester avoir 15 ans ou plus." in errors


def test_creation_rejects_a_json_string_body(client, auth):
    """Same probe, a JSON string this time — both are truthy and both must
    fall back to the same 400, not a 500."""
    res = client.post("/api/voyage", json="just a string", headers=auth)
    assert res.status_code == 400
    errors = res.get_json()["errors"]
    assert "Le consentement est requis." in errors
    assert "Vous devez attester avoir 15 ans ou plus." in errors


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


def test_delete_erases_only_the_callers_own_voyage(client, auth, candidate):
    """delete_voyage has no ownership test of its own beyond _current() —
    final-review finding 1. The neighbour's voyage is created first: a
    handler that always resolved to the oldest row in the table would erase
    the neighbour's voyage instead of the caller's."""
    neighbour_user = _user("voisin-delete@test.fr")
    voyage_b = _voyage(neighbour_user)
    voyage_a = _voyage(candidate)

    res = client.delete("/api/voyage", headers=auth)
    assert res.status_code == 200
    assert Voyage.query.get(voyage_a.id) is None
    assert Voyage.query.get(voyage_b.id) is not None


def test_deleting_a_voyage_still_referenced_by_an_analysis_sets_it_null(client, auth, candidate):
    """The regression test for the FK defect analyses.voyage_id was missing
    an ondelete action for. Under FK enforcement, deleting a voyage an
    analysis still points at used to raise an uncaught IntegrityError (would
    be a 500 in production) because the constraint defaulted to no action.
    ondelete="SET NULL" (analysis.py) plus the handler's own try/except mean
    the erasure still succeeds and only the dangling link is cleared -- the
    analysis itself, the person's own report and its B2G traceability row,
    is never touched."""
    voyage = _voyage(candidate)
    analysis = Analysis(user_id=candidate.id, voyage_id=voyage.id, status="success")
    _db.session.add(analysis)
    _db.session.commit()

    res = client.delete("/api/voyage", headers=auth)
    assert res.status_code == 200
    assert res.get_json()["message"] == "Voyage supprimé."
    assert Voyage.query.get(voyage.id) is None

    refreshed = Analysis.query.get(analysis.id)
    assert refreshed is not None
    assert refreshed.voyage_id is None


def test_deleting_a_voyage_through_the_endpoint_still_erases_its_notes(client, auth, candidate):
    """Same cascade as test_deleting_a_voyage_erases_its_notes above, but
    through the actual DELETE /api/voyage handler and with FK enforcement on
    -- voyage_notes' own ondelete="CASCADE" must still let this go through
    now that voyage_id -> voyages.id violations are no longer silently
    ignored by SQLite."""
    counselor = _user("note-cascade-endpoint@test.fr", role="counselor")
    voyage = _voyage(candidate)
    _db.session.add(VoyageNote(voyage_id=voyage.id, counselor_id=counselor.id, body="vu"))
    _db.session.commit()

    res = client.delete("/api/voyage", headers=auth)
    assert res.status_code == 200
    assert Voyage.query.get(voyage.id) is None
    assert VoyageNote.query.count() == 0


def test_deleting_an_unreferenced_voyage_still_returns_200(client, auth, candidate):
    """No analysis ever pointed at this voyage: erasure must not regress
    into the IntegrityError guard's 409 -- that guard is a safety net for a
    database-level conflict, not the everyday path."""
    voyage = _voyage(candidate)
    res = client.delete("/api/voyage", headers=auth)
    assert res.status_code == 200
    assert res.get_json()["message"] == "Voyage supprimé."
    assert Voyage.query.get(voyage.id) is None


# ── GET / PUT /api/voyage/responses ──────────────────────────────────────────

def _open_voyage(client, auth):
    client.post("/api/voyage", json={"consent": True, "age_attested": True}, headers=auth)
    return Voyage.query.one()


def test_responses_start_empty_and_come_back_whole(client, auth):
    _open_voyage(client, auth)
    res = client.get("/api/voyage/responses", headers=auth)
    assert res.status_code == 200
    assert res.get_json()["responses"] == {"answers": {}, "billets": {}}


def test_responses_are_only_ever_the_callers_own(client, auth, candidate):
    """get_responses serves the raw psychometric answers with no ownership
    check of its own (final-review finding 1) — the worst of the six missed
    handlers, since nothing else in the handler would catch a caller getting
    back someone else's answers. Two candidates, each with distinct stored
    answers, each GET must return only their own. The neighbour's voyage is
    created first, so a handler that always resolved to the oldest row in
    the table would fail this in the caller's direction."""
    neighbour_user = _user("voisin-responses@test.fr")
    voyage_b = _voyage(neighbour_user)
    voyage_b.responses = {"answers": {"S0-01": False}, "billets": {}}
    voyage_a = _voyage(candidate)
    voyage_a.responses = {"answers": {"S0-01": True}, "billets": {}}
    _db.session.commit()

    res = client.get("/api/voyage/responses", headers=auth)
    assert res.get_json()["responses"]["answers"] == {"S0-01": True}

    neighbour = _headers(neighbour_user)
    res = client.get("/api/voyage/responses", headers=neighbour)
    assert res.get_json()["responses"]["answers"] == {"S0-01": False}


def test_responses_without_a_voyage_are_a_404(client, auth):
    assert client.get("/api/voyage/responses", headers=auth).status_code == 404
    res = client.put("/api/voyage/responses", json={"answers": {}}, headers=auth)
    assert res.status_code == 404
    assert res.get_json()["error"] == "Aucun voyage en cours."


def test_a_put_merges_rather_than_replaces(client, auth):
    """Every « Suivant » saves; a lost connection must cost one scene, not the
    whole session."""
    _open_voyage(client, auth)
    client.put("/api/voyage/responses", json={"answers": {"S0-01": True}}, headers=auth)
    res = client.put("/api/voyage/responses", json={"answers": {"S0-02": False}}, headers=auth)
    assert res.status_code == 200
    assert res.get_json()["responses"]["answers"] == {"S0-01": True, "S0-02": False}


def test_put_responses_writes_into_the_callers_own_voyage(client, auth, candidate):
    """put_responses has no ownership test of its own beyond _current() —
    final-review finding 1. The neighbour's voyage is created first: a
    handler that always resolved to the oldest row in the table would write
    the caller's answer into the neighbour's row instead of leaving it
    untouched."""
    neighbour_user = _user("voisin-put@test.fr")
    voyage_b = _voyage(neighbour_user)
    voyage_a = _voyage(candidate)

    res = client.put("/api/voyage/responses", json={"answers": {"S0-01": True}}, headers=auth)
    assert res.status_code == 200

    assert Voyage.query.get(voyage_a.id).responses["answers"] == {"S0-01": True}
    assert Voyage.query.get(voyage_b.id).responses["answers"] == {}


def test_a_put_returns_the_full_merged_set(client, auth):
    """So the player can reconcile after a reconnection without a second call.

    Exact equality against what was sent, not a count — a count would still
    pass if the merge scrambled or shifted the item ids, since it only
    matters here that the two sets have the same size.
    """
    _open_voyage(client, auth)
    sent = _answers_for("0")
    client.put("/api/voyage/responses", json={"answers": sent}, headers=auth)
    res = client.put("/api/voyage/responses",
                     json={"billets": {"0": {"surprise": "je n'aime pas le bureau"}}},
                     headers=auth)
    body = res.get_json()["responses"]
    assert body["answers"] == sent
    assert body["billets"]["0"]["surprise"] == "je n'aime pas le bureau"


def test_an_unknown_item_id_is_dropped_not_rejected(client, auth):
    _open_voyage(client, auth)
    res = client.put("/api/voyage/responses",
                     json={"answers": {"S0-01": True, "S9-99": "Z"}}, headers=auth)
    assert res.status_code == 200
    assert res.get_json()["responses"]["answers"] == {"S0-01": True}


def test_a_known_item_with_a_bad_value_is_rejected(client, auth):
    """A checklist row is a boolean and a scene is one of its own letters;
    anything else means the client and the bank have drifted."""
    _open_voyage(client, auth)
    res = client.put("/api/voyage/responses", json={"answers": {"S0-01": "oui"}}, headers=auth)
    assert res.status_code == 400
    assert res.get_json()["errors"] == ["Réponse invalide pour S0-01."]
    assert Voyage.query.one().responses["answers"] == {}


def test_billet_fields_outside_the_session_are_dropped(client, auth):
    _open_voyage(client, auth)
    res = client.put("/api/voyage/responses", json={
        "billets": {"0": {"surprise": "ok", "inventé": "x"}, "9": {"a": "b"}},
    }, headers=auth)
    assert res.status_code == 200
    billets = res.get_json()["responses"]["billets"]
    assert billets == {"0": {"surprise": "ok"}}


def test_a_non_scalar_billet_value_is_dropped_not_stringified(client, auth):
    """The billet is quoted into the portrait prompt as the candidate's own
    words, and shown on the counselor's sheet — a stringified dict must never
    arrive there looking like something a person typed. Both fields ("top3"
    and "surprise") are known keys for session 0, so this exercises the
    value-type check and not the unknown-key drop; the sibling scalar field
    must still be saved, proving the one field is dropped rather than the
    whole billet."""
    _open_voyage(client, auth)
    res = client.put("/api/voyage/responses", json={
        "billets": {"0": {
            "surprise": "je n'aime pas le bureau",
            "top3": {"nested": "x"},
        }},
    }, headers=auth)
    assert res.status_code == 200
    billet = res.get_json()["responses"]["billets"]["0"]
    assert billet == {"surprise": "je n'aime pas le bureau"}
    assert "top3" not in billet

    res2 = client.put("/api/voyage/responses", json={
        "billets": {"0": {"top3": ["a", "b"]}},
    }, headers=auth)
    assert res2.status_code == 200
    assert "top3" not in res2.get_json()["responses"]["billets"]["0"]

    stored = Voyage.query.one().responses["billets"]["0"]
    assert stored == {"surprise": "je n'aime pas le bureau"}


def test_an_empty_put_is_a_no_op(client, auth):
    _open_voyage(client, auth)
    res = client.put("/api/voyage/responses", json={}, headers=auth)
    assert res.status_code == 200
    assert res.get_json()["responses"] == {"answers": {}, "billets": {}}


def test_answers_for_a_locked_session_are_refused_before_anything_is_written(client, auth):
    _open_voyage(client, auth)
    res = client.put("/api/voyage/responses",
                     json={"answers": {"S0-01": True, "S1-1": "A"}}, headers=auth)
    assert res.status_code == 403
    assert res.get_json()["error"] == LOCK_CODE
    assert Voyage.query.one().responses["answers"] == {}


def test_the_answers_column_holds_ciphertext_after_a_real_save(client, auth):
    """The route-level half of the guarantee: what the API writes is what the
    DB export cannot read."""
    _open_voyage(client, auth)
    client.put("/api/voyage/responses", json={
        "answers": {"S0-01": True},
        "billets": {"0": {"surprise": "je déteste le bureau"}},
    }, headers=auth)
    row = _db.session.execute(_db.text("SELECT responses_encrypted FROM voyages")).first()
    assert "S0-01" not in row[0]
    assert "bureau" not in row[0]
    assert Voyage.query.one().responses["answers"]["S0-01"] is True


def test_a_partial_save_merges_at_the_persistence_layer(client, auth):
    """Two separate PUTs — one carrying only answers, one only billets — must
    both survive in the row scoring reads. The proof lives in a fresh query
    against the (decrypted) column, not just in what the second response
    echoes back, so a merge bug that only fooled the response body would still
    be caught here."""
    voyage = _open_voyage(client, auth)
    client.put("/api/voyage/responses", json={"answers": {"S0-01": True}}, headers=auth)
    client.put("/api/voyage/responses",
               json={"billets": {"0": {"surprise": "je n'aime pas le bureau"}}},
               headers=auth)

    stored = Voyage.query.get(voyage.id).responses
    assert stored["answers"] == {"S0-01": True}
    assert stored["billets"]["0"]["surprise"] == "je n'aime pas le bureau"


def test_malformed_answers_shapes_are_ignored_not_stored(client, auth):
    """Phase-0 trap: scoring._answers() fail-softs to {} on a wrongly-shaped
    payload, so a route that ever writes something other than a dict under
    "answers" silently erases the person's work with no error anywhere. A
    list, and a literal JSON null body, must both be treated like an absent
    key rather than corrupting what is already saved."""
    voyage = _open_voyage(client, auth)
    client.put("/api/voyage/responses", json={"answers": {"S0-01": True}}, headers=auth)

    res = client.put("/api/voyage/responses", json={"answers": ["S0-02"]}, headers=auth)
    assert res.status_code == 200
    assert res.get_json()["responses"]["answers"] == {"S0-01": True}

    res = client.put("/api/voyage/responses", data="null",
                     content_type="application/json", headers=auth)
    assert res.status_code == 200
    assert res.get_json()["responses"]["answers"] == {"S0-01": True}

    stored = Voyage.query.get(voyage.id).responses
    assert stored["answers"] == {"S0-01": True}


def test_a_non_object_body_is_a_400_not_a_500(client, auth):
    """The exact regression a reviewer caught in Task 8: request.get_json()
    can return a list or a string when the client sends well-formed JSON of
    the wrong shape. `or {}` lets both through as truthy, and the next
    `data.get(...)` call then raises AttributeError — an unhandled 500 in
    production, since app/__init__.py registers no error handler for it.
    A JSON array and a JSON string must both be refused as ordinary bad
    input, with the route's own French message, and must not touch the row."""
    voyage = _open_voyage(client, auth)
    client.put("/api/voyage/responses", json={"answers": {"S0-01": True}}, headers=auth)

    for body in ([1, 2, 3], "just a string"):
        res = client.put("/api/voyage/responses", json=body, headers=auth)
        assert res.status_code == 400
        assert res.get_json()["error"] == "Corps de requête invalide."

    stored = Voyage.query.get(voyage.id).responses
    assert stored["answers"] == {"S0-01": True}


# ── POST /api/voyage/sessions/<n>/complete ───────────────────────────────────

from unittest.mock import patch  # noqa: E402  (kept beside the tests that use it)


def _play_session_zero(client, auth):
    client.put("/api/voyage/responses", json={"answers": _answers_for("0")}, headers=auth)
    with patch("app.routes.voyage._spawn_micro") as spawn:
        res = client.post("/api/voyage/sessions/0/complete", headers=auth)
    return res, spawn


def test_an_unknown_session_is_rejected(client, auth):
    _open_voyage(client, auth)
    res = client.post("/api/voyage/sessions/9/complete", headers=auth)
    assert res.status_code == 400
    assert res.get_json()["error"] == "Session inconnue."


def test_completing_needs_every_item_of_the_session(client, auth):
    _open_voyage(client, auth)
    first, second = bank.items("0")[0]["id"], bank.items("0")[1]["id"]
    client.put("/api/voyage/responses", json={"answers": {first: True}}, headers=auth)

    res = client.post("/api/voyage/sessions/0/complete", headers=auth)
    assert res.status_code == 400
    errors = res.get_json()["errors"]
    assert errors[0] == "Réponses manquantes."
    assert second in errors[1:]
    assert first not in errors[1:]


def test_completing_session_zero_flips_the_status_and_asks_for_the_phrase(client, auth):
    _open_voyage(client, auth)
    res, spawn = _play_session_zero(client, auth)
    assert res.status_code == 200
    payload = res.get_json()["voyage"]
    assert payload["status"] == STATUS_S0
    assert payload["sessions_completed"] == ["0"]
    assert payload["micro_status"] == "generating"
    assert payload["share_token"] is None
    spawn.assert_called_once_with(Voyage.query.one().id)


def test_a_session_cannot_be_completed_twice(client, auth):
    _open_voyage(client, auth)
    _play_session_zero(client, auth)
    res = client.post("/api/voyage/sessions/0/complete", headers=auth)
    assert res.status_code == 409
    assert res.get_json()["error"] == "Cette session est déjà terminée."
    assert Voyage.query.one().sessions_completed == ["0"]


def test_session_one_needs_the_code_then_the_profile(client, auth, candidate):
    _open_voyage(client, auth)
    _play_session_zero(client, auth)

    res = client.post("/api/voyage/sessions/1/complete", headers=auth)
    assert res.status_code == 403
    assert res.get_json()["error"] == LOCK_CODE

    voyage = Voyage.query.one()
    voyage.counselor_code_id = _code().id
    _db.session.commit()
    res = client.post("/api/voyage/sessions/1/complete", headers=auth)
    assert res.status_code == 403
    assert res.get_json()["error"] == LOCK_PROFILE


def test_sessions_must_be_completed_in_order(client, auth, candidate):
    _open_voyage(client, auth)
    _play_session_zero(client, auth)
    voyage = Voyage.query.one()
    voyage.counselor_code_id = _code().id
    _db.session.add(Profile(user_id=candidate.id, prenom="Marie", tranche_age="25_34"))
    _db.session.commit()

    client.put("/api/voyage/responses", json={"answers": _answers_for("2")}, headers=auth)
    res = client.post("/api/voyage/sessions/2/complete", headers=auth)
    assert res.status_code == 409
    assert res.get_json()["error"] == LOCK_ORDER


def _play_to_the_end(client, auth, candidate):
    """Consent → S0 → code + profile → S1..S5. Returns the S5 response and the
    patched portrait spawn."""
    _open_voyage(client, auth)
    _play_session_zero(client, auth)
    voyage = Voyage.query.one()
    voyage.counselor_code_id = _code().id
    _db.session.add(Profile(user_id=candidate.id, prenom="Marie", tranche_age="25_34"))
    _db.session.commit()

    for n in ("1", "2", "3", "4"):
        client.put("/api/voyage/responses", json={"answers": _answers_for(n)}, headers=auth)
        assert client.post(f"/api/voyage/sessions/{n}/complete", headers=auth).status_code == 200

    client.put("/api/voyage/responses", json={"answers": _answers_for("5")}, headers=auth)
    with patch("app.routes.voyage._spawn_portrait") as spawn:
        res = client.post("/api/voyage/sessions/5/complete", headers=auth)
    return res, spawn


def test_the_middle_sessions_change_no_status(client, auth, candidate):
    _open_voyage(client, auth)
    _play_session_zero(client, auth)
    voyage = Voyage.query.one()
    voyage.counselor_code_id = _code().id
    _db.session.add(Profile(user_id=candidate.id, prenom="Marie", tranche_age="25_34"))
    _db.session.commit()

    client.put("/api/voyage/responses", json={"answers": _answers_for("1")}, headers=auth)
    res = client.post("/api/voyage/sessions/1/complete", headers=auth)
    assert res.status_code == 200
    payload = res.get_json()["voyage"]
    assert payload["status"] == STATUS_S0
    assert payload["sessions_completed"] == ["0", "1"]
    assert payload["portrait_status"] == "none"


def test_completing_session_five_finishes_the_voyage(client, auth, candidate):
    res, spawn = _play_to_the_end(client, auth, candidate)
    assert res.status_code == 200
    payload = res.get_json()["voyage"]
    assert payload["status"] == STATUS_TERMINE
    assert payload["sessions_completed"] == ["0", "1", "2", "3", "4", "5"]
    assert payload["completed_at"] is not None
    assert payload["portrait_status"] == "generating"
    assert len(payload["share_token"]) == 32
    spawn.assert_called_once_with(Voyage.query.one().id)


def test_completing_without_a_voyage_is_a_404(client, auth):
    res = client.post("/api/voyage/sessions/0/complete", headers=auth)
    assert res.status_code == 404
    assert res.get_json()["error"] == "Aucun voyage en cours."


def test_completing_a_session_closes_only_the_callers_own_voyage(client, auth, candidate):
    """complete_session has no ownership test of its own beyond _current() —
    final-review finding 1. The neighbour's voyage is created first, has no
    session-0 answers on file, and stays untouched: a handler that always
    resolved to the oldest row in the table would try to close the
    neighbour's empty session instead and fail with "Réponses manquantes."
    rather than closing the caller's own, answered one."""
    neighbour_user = _user("voisin-complete@test.fr")
    voyage_b = _voyage(neighbour_user)
    voyage_a = _voyage(candidate)

    client.put("/api/voyage/responses", json={"answers": _answers_for("0")}, headers=auth)
    with patch("app.routes.voyage._spawn_micro"):
        res = client.post("/api/voyage/sessions/0/complete", headers=auth)
    assert res.status_code == 200

    assert Voyage.query.get(voyage_a.id).sessions_completed == ["0"]
    assert Voyage.query.get(voyage_b.id).sessions_completed == []


# ── extra coverage: this phase shipped two production 500s already, so these
# probes exist specifically to fail loudly if a similar defect creeps back in.

def test_a_non_numeric_session_id_is_also_a_clean_400(client, auth):
    """bank.SESSION_IDS is a tuple of digit strings; session_lock() does
    str(int(n) - 1) once past that gate, so an unvalidated 'abc' would raise
    ValueError -> 500 instead of a clean 4xx."""
    _open_voyage(client, auth)
    res = client.post("/api/voyage/sessions/abc/complete", headers=auth)
    assert res.status_code == 400
    assert res.get_json()["error"] == "Session inconnue."


def test_completing_the_same_session_twice_leaves_no_duplicate(client, auth):
    """The list column must be reassigned, not appended to in place, and the
    second attempt must not sneak a second '0' into the list even though it
    is refused with a 409."""
    _open_voyage(client, auth)
    _play_session_zero(client, auth)
    client.post("/api/voyage/sessions/0/complete", headers=auth)
    client.post("/api/voyage/sessions/0/complete", headers=auth)
    assert Voyage.query.one().sessions_completed == ["0"]


def test_the_lock_check_is_not_decorative(client, auth, candidate, monkeypatch):
    """Prove the gate actually gates: with session_lock() forced to always
    return None, completing S1 with no counselor code and no profile must
    succeed — showing that without the real gate this request would have
    been let through. Restored immediately after, and never committed."""
    import app.routes.voyage as voyage_routes

    _open_voyage(client, auth)
    _play_session_zero(client, auth)

    # With the real gate: refused outright — session_lock() is checked before
    # the missing-items check, so this needs no answers on file to prove it.
    blocked = client.post("/api/voyage/sessions/1/complete", headers=auth)
    assert blocked.status_code == 403
    assert blocked.get_json()["error"] == LOCK_CODE

    # With the gate stubbed out: the same caller — still no counselor code, no
    # profile — can now both save and complete session 1. This is exactly why
    # the real session_lock() call must never be removed from either route.
    monkeypatch.setattr(voyage_routes, "session_lock", lambda voyage, profile, n: None)
    client.put("/api/voyage/responses", json={"answers": _answers_for("1")}, headers=auth)
    allowed = client.post("/api/voyage/sessions/1/complete", headers=auth)
    assert allowed.status_code == 200
    assert Voyage.query.one().sessions_completed == ["0", "1"]


def test_the_response_carries_no_scoring_or_framework_vocabulary(client, auth):
    """Completing a session must not leak completeness figures, trait names or
    framework names — to_dict()'s pinned 12-key shape is the only thing a
    candidate may see."""
    _open_voyage(client, auth)
    res, _spawn = _play_session_zero(client, auth)
    payload = res.get_json()["voyage"]
    assert set(payload) == TO_DICT_KEYS
    flat = str(payload)
    for forbidden in (
        "riasec", "RIASEC", "big5", "schwartz", "sdt", "axes",
        "completeness", "resultant", "tension", "score",
    ):
        assert forbidden not in flat


# ── POST /api/voyage/micro/retry ─────────────────────────────────────────────

RETRY_URL = "/api/voyage/micro/retry"
NOT_RETRYABLE = "La phrase ne peut pas être relancée."


def _age(voyage, minutes):
    """Push updated_at `minutes` into the past.

    A bulk UPDATE that names the column writes the value given; changing any
    other attribute through the ORM would stamp updated_at back to now through
    its onupdate. Call it last, after every other write to the row.
    """
    voyage_id = voyage.id
    _db.session.query(Voyage).filter_by(id=voyage_id).update(
        {"updated_at": datetime.utcnow() - timedelta(minutes=minutes)},
        synchronize_session=False)
    _db.session.commit()
    _db.session.expire_all()
    return _db.session.get(Voyage, voyage_id)


def _after_session_zero(user, **overrides):
    fields = {"status": STATUS_S0, "sessions_completed": ["0"]}
    fields.update(overrides)
    return _voyage(user, **fields)


def test_the_stall_threshold_is_the_hubs_three_minutes():
    from app.routes import voyage as voyage_routes
    assert voyage_routes.MICRO_RETRY_STALE_MINUTES == 3


def test_retrying_the_phrase_needs_an_account(client):
    assert client.post(RETRY_URL).status_code == 401


def test_retrying_the_phrase_without_a_voyage_is_a_404(client, auth):
    with patch("app.routes.voyage._spawn_micro") as spawn:
        res = client.post(RETRY_URL, headers=auth)
    assert res.status_code == 404
    assert res.get_json() == {"error": "Aucun voyage en cours."}
    spawn.assert_not_called()


def test_the_phrase_cannot_be_retried_before_session_zero_is_complete(client, auth, candidate):
    """micro_status is "error" here on purpose, so the only thing refusing the
    retry is the missing session 0."""
    voyage = _voyage(candidate, micro_status="error")
    with patch("app.routes.voyage._spawn_micro") as spawn:
        res = client.post(RETRY_URL, headers=auth)
    assert res.status_code == 409
    assert res.get_json() == {"error": "Terminez d'abord la session 0."}
    spawn.assert_not_called()
    assert Voyage.query.get(voyage.id).micro_status == "error"


@pytest.mark.parametrize("status, minutes", [
    ("none", 60),           # old enough to pass the stall test if status were ignored
    ("success", 60),
    ("generating", 0),      # a live run
])
def test_a_phrase_that_is_neither_failed_nor_stalled_is_not_relaunched(
        client, auth, candidate, status, minutes):
    voyage = _age(_after_session_zero(candidate, micro_status=status), minutes)
    before = voyage.updated_at
    with patch("app.routes.voyage._spawn_micro") as spawn:
        res = client.post(RETRY_URL, headers=auth)
    assert res.status_code == 409
    assert res.get_json() == {"error": NOT_RETRYABLE}
    spawn.assert_not_called()
    _db.session.expire_all()
    row = Voyage.query.get(voyage.id)
    assert row.micro_status == status
    assert row.updated_at == before


def test_a_failed_phrase_is_relaunched_once_its_status_is_committed(client, auth, candidate):
    """The spawned run re-reads the row on its own connection, so the status
    must already be committed when the spawn happens. The fake spawn reads it
    through a session of its own: an uncommitted "generating" is invisible
    there."""
    from sqlalchemy.orm import Session

    voyage_id = _after_session_zero(candidate, micro_status="error").id
    seen = []

    def spawn_reads_the_row(spawned_id):
        with Session(_db.engine) as fresh:
            seen.append((spawned_id, fresh.get(Voyage, spawned_id).micro_status))

    with patch("app.routes.voyage._spawn_micro", side_effect=spawn_reads_the_row) as spawn:
        res = client.post(RETRY_URL, headers=auth)

    assert res.status_code == 202
    payload = res.get_json()["voyage"]
    assert set(payload) == TO_DICT_KEYS
    assert payload["micro_status"] == "generating"
    spawn.assert_called_once_with(voyage_id)
    assert seen == [(voyage_id, "generating")]


def test_a_phrase_stalled_for_four_minutes_is_relaunched(client, auth, candidate):
    voyage = _age(_after_session_zero(candidate, micro_status="generating"), 4)
    with patch("app.routes.voyage._spawn_micro") as spawn:
        res = client.post(RETRY_URL, headers=auth)
    assert res.status_code == 202
    assert res.get_json()["voyage"]["micro_status"] == "generating"
    spawn.assert_called_once_with(voyage.id)


def test_a_phrase_generating_for_two_minutes_is_left_alone(client, auth, candidate):
    voyage = _age(_after_session_zero(candidate, micro_status="generating"), 2)
    with patch("app.routes.voyage._spawn_micro") as spawn:
        res = client.post(RETRY_URL, headers=auth)
    assert res.status_code == 409
    assert res.get_json() == {"error": NOT_RETRYABLE}
    spawn.assert_not_called()
    assert Voyage.query.get(voyage.id).micro_status == "generating"


def test_relaunching_a_stalled_phrase_restarts_its_clock(client, auth, candidate):
    """A stalled row already reads "generating", so the status assignment alone
    writes nothing and leaves the row looking stalled: a second click would be
    accepted and spawn a second run beside the first."""
    _age(_after_session_zero(candidate, micro_status="generating"), 4)
    with patch("app.routes.voyage._spawn_micro") as spawn:
        first = client.post(RETRY_URL, headers=auth)
        second = client.post(RETRY_URL, headers=auth)
    assert first.status_code == 202
    assert second.status_code == 409
    assert second.get_json() == {"error": NOT_RETRYABLE}
    spawn.assert_called_once()


def test_a_finished_voyage_with_a_failed_phrase_is_still_retryable(client, auth, candidate):
    """The voyage's own status is irrelevant: the phrase is what failed."""
    voyage = _voyage(candidate, status=STATUS_TERMINE,
                     sessions_completed=["0", "1", "2", "3", "4", "5"],
                     micro_status="error", portrait_status="validated")
    with patch("app.routes.voyage._spawn_micro") as spawn:
        res = client.post(RETRY_URL, headers=auth)
    assert res.status_code == 202
    spawn.assert_called_once_with(voyage.id)


def test_a_retry_only_ever_reaches_the_callers_own_voyage(client, auth, candidate):
    """The neighbour's failed phrase is created first, so a handler resolving
    the oldest row in the table would relaunch it; the caller's own phrase
    succeeded and is not retryable."""
    neighbour = _after_session_zero(_user("voisin-retry@test.fr"), micro_status="error")
    _after_session_zero(candidate, micro_status="success")

    with patch("app.routes.voyage._spawn_micro") as spawn:
        res = client.post(RETRY_URL, headers=auth)

    assert res.status_code == 409
    assert res.get_json() == {"error": NOT_RETRYABLE}
    spawn.assert_not_called()
    _db.session.expire_all()
    assert Voyage.query.get(neighbour.id).micro_status == "error"


# ── POST /api/voyage/unlock ──────────────────────────────────────────────────

def _code(active=True, label="Cap Emploi test"):
    from app.models.counselor_code import CounselorCode
    code = CounselorCode(label=label, is_active=active)
    _db.session.add(code)
    _db.session.commit()
    return code


def test_a_valid_code_unlocks_the_later_sessions(client, auth):
    _open_voyage(client, auth)
    code = _code()
    res = client.post("/api/voyage/unlock", json={"code": code.code}, headers=auth)
    assert res.status_code == 200
    assert res.get_json()["voyage"]["has_code"] is True
    # Assert the FK the handler is supposed to write, not the absence of a key
    # to_dict() can never emit: test_to_dict_carries_exactly_twelve_keys already
    # pins the payload shape, so an absence check here passes on a broken handler.
    assert Voyage.query.one().counselor_code_id == code.id
    _db.session.refresh(code)
    assert code.uses_count == 1


def test_the_code_is_normalised_like_an_analysis_unlock(client, auth):
    _open_voyage(client, auth)
    code = _code()
    spaced = f" {code.code[:4].lower()}-{code.code[4:]} "
    assert client.post("/api/voyage/unlock", json={"code": spaced},
                       headers=auth).status_code == 200


def test_an_empty_or_unknown_or_disabled_code_is_refused(client, auth):
    _open_voyage(client, auth)
    res = client.post("/api/voyage/unlock", json={"code": "  "}, headers=auth)
    assert res.status_code == 400
    assert res.get_json()["error"] == "Code requis."

    res = client.post("/api/voyage/unlock", json={"code": "NOPE1234"}, headers=auth)
    assert res.status_code == 400
    assert res.get_json()["error"] == "Code invalide ou désactivé."

    disabled = _code(active=False, label="désactivé")
    res = client.post("/api/voyage/unlock", json={"code": disabled.code}, headers=auth)
    assert res.status_code == 400
    assert Voyage.query.one().has_code is False


def test_unlocking_twice_does_not_burn_a_second_use(client, auth):
    _open_voyage(client, auth)
    first, second = _code(), _code(label="deuxième")
    client.post("/api/voyage/unlock", json={"code": first.code}, headers=auth)
    res = client.post("/api/voyage/unlock", json={"code": second.code}, headers=auth)
    assert res.status_code == 409
    assert res.get_json()["error"] == "Ce voyage est déjà débloqué."
    _db.session.refresh(second)
    assert second.uses_count == 0


def test_unlocking_without_a_voyage_is_a_404(client, auth):
    code = _code()
    res = client.post("/api/voyage/unlock", json={"code": code.code}, headers=auth)
    assert res.status_code == 404


def test_unlock_redeems_the_code_against_only_the_callers_own_voyage(client, auth, candidate):
    """unlock_voyage has no ownership test of its own beyond _current() —
    final-review finding 1. The neighbour's voyage is created first: a
    handler that always resolved to the oldest row in the table would grant
    the code to the neighbour's voyage instead of the caller's."""
    neighbour_user = _user("voisin-unlock@test.fr")
    voyage_b = _voyage(neighbour_user)
    voyage_a = _voyage(candidate)

    code = _code()
    res = client.post("/api/voyage/unlock", json={"code": code.code}, headers=auth)
    assert res.status_code == 200

    assert Voyage.query.get(voyage_a.id).counselor_code_id == code.id
    assert Voyage.query.get(voyage_b.id).counselor_code_id is None


def test_unlock_rejects_a_json_array_body(client, auth):
    """Same probe as test_a_non_object_body_is_a_400_not_a_500 on /responses:
    request.get_json(silent=True) or {} lets a JSON array through as truthy,
    and the next .get("code") call then raises AttributeError -> an
    unhandled 500. Coerced to {}, this must fall through to the ordinary
    "code missing" 400, never a 500."""
    _open_voyage(client, auth)
    res = client.post("/api/voyage/unlock", json=[1, 2, 3], headers=auth)
    assert res.status_code == 400
    assert res.get_json()["error"] == "Code requis."


def test_unlock_rejects_a_non_string_code_field(client, auth):
    """A "code" field that parsed as JSON but is not a string (here a list)
    must not reach str.strip() and crash the request into a 500."""
    _open_voyage(client, auth)
    res = client.post("/api/voyage/unlock", json={"code": ["A", "B"]}, headers=auth)
    assert res.status_code == 400
    assert res.get_json()["error"] == "Code requis."


def test_unlock_needs_an_account(client):
    assert client.post("/api/voyage/unlock", json={"code": "ABCD1234"}).status_code == 401


# ── GET /api/voyage/portrait ─────────────────────────────────────────────────

def test_the_portrait_waits_for_a_counselor(client, auth, candidate):
    """Decision 9: the human step the paper protocol protects — restitution —
    stays human. A draft is not a portrait."""
    voyage = _voyage(candidate, status=STATUS_TERMINE, portrait_status="draft",
                     share_token="tok-draft")
    voyage.portrait = {"sections": {k: f"texte {k}" for k in PORTRAIT_KEYS},
                       "flags": [], "edited": False}
    _db.session.commit()

    res = client.get("/api/voyage/portrait", headers=auth)
    assert res.status_code == 409
    body = res.get_json()
    assert body["error"] == "Votre portrait est en attente de validation."
    assert body["status"] == "draft"
    assert "texte accroche" not in str(body)


def test_a_validated_portrait_is_served_with_its_six_sections(client, auth, candidate):
    voyage = _voyage(candidate, status=STATUS_TERMINE, portrait_status="validated",
                     share_token="tok-ok", portrait_validated_at=datetime(2026, 9, 12, 10, 4))
    voyage.portrait = {"sections": {k: f"texte {k}" for k in PORTRAIT_KEYS},
                       "snapshot": {"s0": {"axes": {}}}, "flags": ["vocabulaire"],
                       "edited": True}
    _db.session.commit()

    res = client.get("/api/voyage/portrait", headers=auth)
    assert res.status_code == 200
    portrait = res.get_json()["portrait"]
    assert set(portrait) == {"sections", "validated_at"}
    assert set(portrait["sections"]) == set(PORTRAIT_KEYS)
    assert portrait["validated_at"] == "2026-09-12T10:04:00"
    # The counselor's working material stays on the counselor's side.
    assert "snapshot" not in str(portrait)
    assert "vocabulaire" not in str(portrait)


def test_the_portrait_without_a_voyage_is_a_404(client, auth):
    assert client.get("/api/voyage/portrait", headers=auth).status_code == 404


def test_portrait_needs_an_account(client):
    assert client.get("/api/voyage/portrait").status_code == 401


def test_the_portrait_is_only_ever_the_callers_own(client, auth, candidate):
    """No candidate endpoint takes an id from the client. Two candidates each
    have a validated portrait; each caller must see only their own six
    sections, never the neighbour's.

    Both directions matter: `candidate`'s voyage is created first, so a
    handler that always resolved to the oldest row in the table (the mutation
    final review probes for) would still pass the first assertion below by
    coincidence. The second assertion — the neighbour, whose voyage is
    created second, seeing their own text — is what actually catches that
    mutation."""
    voyage_a = _voyage(candidate, status=STATUS_TERMINE, portrait_status="validated",
                       share_token="tok-a")
    voyage_a.portrait = {"sections": {k: "texte A" for k in PORTRAIT_KEYS}}
    neighbour_user = _user("voisin-portrait@test.fr")
    voyage_b = _voyage(neighbour_user, status=STATUS_TERMINE, portrait_status="validated",
                       share_token="tok-b")
    voyage_b.portrait = {"sections": {k: "texte B" for k in PORTRAIT_KEYS}}
    _db.session.commit()

    res = client.get("/api/voyage/portrait", headers=auth)
    assert res.get_json()["portrait"]["sections"]["accroche"] == "texte A"

    neighbour = _headers(neighbour_user)
    res = client.get("/api/voyage/portrait", headers=neighbour)
    assert res.get_json()["portrait"]["sections"]["accroche"] == "texte B"


# ── counselor: role AND token ────────────────────────────────────────────────

@pytest.fixture
def counselor_auth(app):
    """(user, headers) — most tests only need the headers; a few (identity,
    ownership) need the user row too."""
    counselor = _user("conseiller@test.fr", role="counselor")
    return counselor, _headers(counselor)


@pytest.fixture
def sheet(candidate):
    """A finished voyage with a portrait draft, built directly: walking six
    sessions through the API again would test the player, not the gate."""
    voyage = _voyage(
        candidate,
        status=STATUS_TERMINE,
        sessions_completed=["0", "1", "2", "3", "4", "5"],
        share_token="tok-conseiller",
        portrait_status="draft",
        completed_at=datetime.utcnow(),
    )
    voyage.responses = {"answers": _answers_for("0"), "billets": {}}
    voyage.portrait = {
        # "secret_snapshot" is not a PORTRAIT_KEYS section: it is planted here
        # to prove _counselor_portrait's `if k in PORTRAIT_KEYS` filter is
        # live, not a pass-through dict(sections) (Task 12 review, finding 4).
        "sections": {**{k: f"texte {k}" for k in PORTRAIT_KEYS},
                    "secret_snapshot": "ne doit jamais sortir"},
        "snapshot": {}, "flags": [], "edited": False,
        "prompt_version_id": "pv-1", "tokens_in": 10, "tokens_out": 20, "error": None,
    }
    _db.session.add(Profile(user_id=candidate.id, prenom="Marie",
                            tranche_age="25_34", situation="en_recherche"))
    _db.session.commit()
    return voyage


def test_the_sheet_is_never_reachable_by_link_alone(client, sheet, auth, counselor_auth):
    """Unlike /api/c/<token> for an analysis. Deliberate: this is a
    psychometric read-out, not a report the person already has."""
    _, counselor_auth = counselor_auth
    assert client.get("/api/voyage/c/tok-conseiller").status_code == 401
    res = client.get("/api/voyage/c/tok-conseiller", headers=auth)
    assert res.status_code == 403
    assert res.get_json()["error"] == "Accès non autorisé."
    assert client.get("/api/voyage/c/tok-conseiller", headers=counselor_auth).status_code == 200


def test_an_unknown_token_is_a_404(client, counselor_auth):
    _, counselor_auth = counselor_auth
    res = client.get("/api/voyage/c/nope", headers=counselor_auth)
    assert res.status_code == 404
    assert res.get_json()["error"] == "Voyage introuvable."


def test_an_unknown_token_404s_even_when_voyages_exist(client, sheet, counselor_auth):
    """Same probe as test_an_unknown_token_is_a_404, but against a database
    that is not empty. The empty-DB version's 404 is structurally true for
    any token at all and does not exercise the lookup by token; this one
    fails if by_token is replaced by e.g. Voyage.query.first()."""
    _, counselor_auth = counselor_auth
    res = client.get("/api/voyage/c/nope", headers=counselor_auth)
    assert res.status_code == 404
    assert res.get_json()["error"] == "Voyage introuvable."


def test_a_token_reaches_only_its_own_voyage(client, sheet, counselor_auth):
    """The security property "role AND token" pins on: the token must
    resolve *its* voyage, not merely *a* voyage. Two voyages exist, each
    with its own token, owner and section text; each token must open only
    its own row."""
    counselor, counselor_auth = counselor_auth
    neighbour = _user("voisin-conseiller@test.fr")
    voisin = _voyage(
        neighbour, status=STATUS_TERMINE,
        sessions_completed=["0", "1", "2", "3", "4", "5"],
        share_token="tok-voisin", portrait_status="draft",
        completed_at=datetime.utcnow(),
    )
    voisin.responses = {"answers": _answers_for("0"), "billets": {}}
    voisin.portrait = {"sections": {k: f"voisin {k}" for k in PORTRAIT_KEYS},
                       "flags": [], "edited": False}
    _db.session.add(Profile(user_id=neighbour.id, prenom="Paul",
                            tranche_age="35_44", situation="en_poste"))
    _db.session.commit()

    res_a = client.get("/api/voyage/c/tok-conseiller", headers=counselor_auth)
    body_a = res_a.get_json()["voyage"]
    assert body_a["id"] == sheet.id
    assert body_a["prenom"] == "Marie"
    assert body_a["portrait"]["sections"]["accroche"] == "texte accroche"

    res_b = client.get("/api/voyage/c/tok-voisin", headers=counselor_auth)
    body_b = res_b.get_json()["voyage"]
    assert body_b["id"] == voisin.id
    assert body_b["prenom"] == "Paul"
    assert body_b["portrait"]["sections"]["accroche"] == "voisin accroche"


def test_the_sheet_carries_the_profile_the_synthesis_and_the_draft(client, sheet, counselor_auth):
    _, counselor_auth = counselor_auth
    res = client.get("/api/voyage/c/tok-conseiller", headers=counselor_auth)
    body = res.get_json()["voyage"]
    assert set(body) == {"id", "status", "prenom", "tranche_age", "situation",
                         "synthesis", "portrait"}
    assert body["prenom"] == "Marie"
    # Contract literal (§ B.5), not bank.SCORING_VERSION: deriving the
    # expectation from the code under test would let a drift in the constant
    # pass silently.
    assert body["synthesis"]["scoring_version"] == "cahier-2026-09"
    assert body["synthesis"]["s0"] is not None
    assert body["synthesis"]["riasec"] is None          # sessions 1-5 unanswered
    assert set(body["portrait"]) == {"status", "sections", "flags", "edited", "validated_at"}
    assert body["portrait"]["status"] == "draft"


def test_the_sheet_filters_unknown_keys_out_of_the_stored_sections(client, sheet, counselor_auth):
    """_counselor_portrait's `if k in PORTRAIT_KEYS` filter, not a
    pass-through dict(sections): the sheet fixture plants a
    "secret_snapshot" key inside `sections` precisely to prove this."""
    _, counselor_auth = counselor_auth
    res = client.get("/api/voyage/c/tok-conseiller", headers=counselor_auth)
    sections = res.get_json()["voyage"]["portrait"]["sections"]
    assert set(sections) == set(PORTRAIT_KEYS)


def test_the_sheet_never_carries_the_generation_bookkeeping(client, sheet, counselor_auth):
    _, counselor_auth = counselor_auth
    body = client.get("/api/voyage/c/tok-conseiller", headers=counselor_auth).get_data(as_text=True)
    assert "prompt_version_id" not in body
    assert "tokens_in" not in body


# ── editing, regenerating, validating ────────────────────────────────────────

def _sections(**overrides):
    sections = {k: f"nouveau {k}" for k in PORTRAIT_KEYS}
    sections.update(overrides)
    return sections


def test_editing_replaces_all_six_sections_and_marks_the_draft_edited(client, sheet, counselor_auth):
    _, counselor_auth = counselor_auth
    res = client.put("/api/voyage/c/tok-conseiller/portrait",
                     json={"sections": _sections()}, headers=counselor_auth)
    assert res.status_code == 200
    portrait = res.get_json()["portrait"]
    assert portrait["edited"] is True
    assert portrait["sections"]["accroche"] == "nouveau accroche"


def test_editing_refuses_a_missing_blank_or_unknown_section(client, sheet, counselor_auth):
    _, counselor_auth = counselor_auth
    res = client.put("/api/voyage/c/tok-conseiller/portrait",
                     json={"sections": _sections(accroche="   ")}, headers=counselor_auth)
    assert res.status_code == 400
    assert res.get_json()["errors"] == ["Section manquante ou vide : accroche."]

    partial = _sections()
    partial.pop("chemins")
    partial["intro"] = "x"
    res = client.put("/api/voyage/c/tok-conseiller/portrait",
                     json={"sections": partial}, headers=counselor_auth)
    assert res.status_code == 400
    errors = res.get_json()["errors"]
    assert "Section inconnue : intro." in errors
    assert "Section manquante ou vide : chemins." in errors


def test_editing_refuses_a_non_string_section_value(client, sheet, counselor_auth):
    """Final-review finding 4: `str(sections.get(key) or "").strip()` makes a
    dict or a list non-empty, so it passed the "manquante ou vide" check and
    was then stored as str({'nested': 'x'}) — reaching the candidate as their
    own portrait text. Both shapes must be refused, and the portrait already
    on file must be left exactly as it was."""
    _, counselor_auth = counselor_auth
    before = dict(Voyage.query.one().portrait["sections"])

    res = client.put("/api/voyage/c/tok-conseiller/portrait",
                     json={"sections": _sections(accroche={"nested": "x"})},
                     headers=counselor_auth)
    assert res.status_code == 400
    assert res.get_json()["errors"] == ["Section invalide : accroche."]

    res = client.put("/api/voyage/c/tok-conseiller/portrait",
                     json={"sections": _sections(qui_tu_es=[1, 2])},
                     headers=counselor_auth)
    assert res.status_code == 400
    assert res.get_json()["errors"] == ["Section invalide : qui_tu_es."]

    assert Voyage.query.one().portrait["sections"] == before


def test_editing_rejects_a_json_array_body(client, sheet, counselor_auth):
    """Same probe as the candidate-side handlers (put_responses, unlock):
    request.get_json(silent=True) or {} lets a JSON array survive as truthy,
    and the next .get("sections") call then raises AttributeError -> an
    unhandled 500. Coerced to {}, this must fall through to the ordinary
    "all six sections missing" 400, never a 500."""
    _, counselor_auth = counselor_auth
    res = client.put("/api/voyage/c/tok-conseiller/portrait",
                     json=[1, 2, 3], headers=counselor_auth)
    assert res.status_code == 400
    errors = res.get_json()["errors"]
    assert len(errors) == len(PORTRAIT_KEYS)
    assert "Section manquante ou vide : accroche." in errors


def test_editing_a_portrait_that_does_not_exist_yet_is_a_409(client, candidate, counselor_auth):
    _, counselor_auth = counselor_auth
    _voyage(candidate, status=STATUS_TERMINE, share_token="tok-vide",
            portrait_status="generating")
    res = client.put("/api/voyage/c/tok-vide/portrait",
                     json={"sections": _sections()}, headers=counselor_auth)
    assert res.status_code == 409
    assert res.get_json()["error"] == "Aucun portrait à modifier."


def test_regenerating_a_draft_spawns_the_run(client, sheet, counselor_auth):
    _, counselor_auth = counselor_auth
    with patch("app.routes.voyage._spawn_portrait") as spawn:
        res = client.post("/api/voyage/c/tok-conseiller/portrait/regenerate",
                          headers=counselor_auth)
    assert res.status_code == 202
    assert res.get_json()["portrait"] == {"status": "generating", "sections": {},
                                          "flags": [], "edited": False, "validated_at": None}
    spawn.assert_called_once_with(sheet.id)
    assert Voyage.query.one().portrait_status == "generating"


def test_a_validated_portrait_is_not_regenerated(client, sheet, counselor_auth):
    _, counselor_auth = counselor_auth
    client.post("/api/voyage/c/tok-conseiller/validate", headers=counselor_auth)
    res = client.post("/api/voyage/c/tok-conseiller/portrait/regenerate", headers=counselor_auth)
    assert res.status_code == 409
    assert res.get_json()["error"] == "Le portrait ne peut plus être régénéré."


def test_validating_records_who_did_it(client, sheet, counselor_auth):
    """Mutating validated_by_id to record the candidate (voyage.user_id)
    instead of get_jwt_identity() must fail here — an `is not None` check
    alone cannot tell the two apart."""
    counselor, counselor_auth = counselor_auth
    res = client.post("/api/voyage/c/tok-conseiller/validate", headers=counselor_auth)
    assert res.status_code == 200
    portrait = res.get_json()["portrait"]
    assert portrait["status"] == "validated"
    assert portrait["validated_at"] is not None

    row = Voyage.query.one()
    assert row.validated_by_id == str(counselor.id)
    assert row.portrait_validated_at is not None


def test_a_portrait_is_validated_once(client, sheet, counselor_auth):
    _, counselor_auth = counselor_auth
    client.post("/api/voyage/c/tok-conseiller/validate", headers=counselor_auth)
    res = client.post("/api/voyage/c/tok-conseiller/validate", headers=counselor_auth)
    assert res.status_code == 409
    assert res.get_json()["error"] == "Aucun portrait à valider."


def test_validating_an_incomplete_portrait_is_refused(client, candidate, counselor_auth):
    """A generation run that only produced some of the six sections must not
    be validatable: get_portrait has no completeness check of its own (it
    trusts portrait_status == "validated"), so this is the last point that
    can stop an empty/partial portrait from reaching the candidate behind a
    200. A blank string counts as missing, same as portrait_sections."""
    _, counselor_auth = counselor_auth
    voyage = _voyage(candidate, status=STATUS_TERMINE, share_token="tok-incomplet",
                     portrait_status="draft")
    sections = {k: f"texte {k}" for k in PORTRAIT_KEYS}
    sections["chemins"] = ""
    voyage.portrait = {"sections": sections, "flags": [], "edited": False}
    _db.session.commit()

    res = client.post("/api/voyage/c/tok-incomplet/validate", headers=counselor_auth)
    assert res.status_code == 409
    assert res.get_json()["error"] == "Le portrait est incomplet : impossible de le valider."

    row = Voyage.query.get(voyage.id)
    assert row.portrait_status == "draft"
    assert row.portrait_validated_at is None
    assert row.validated_by_id is None


def test_validation_is_what_opens_the_candidate_endpoint(client, sheet, auth, counselor_auth):
    _, counselor_auth = counselor_auth
    assert client.get("/api/voyage/portrait", headers=auth).status_code == 409
    client.post("/api/voyage/c/tok-conseiller/validate", headers=counselor_auth)
    res = client.get("/api/voyage/portrait", headers=auth)
    assert res.status_code == 200
    assert res.get_json()["portrait"]["sections"]["accroche"] == "texte accroche"


def test_a_validated_portrait_reaches_the_candidate_with_all_six_sections_intact(
        client, sheet, auth, counselor_auth):
    """Not just that six keys exist: the exact text the counselor validated
    must be what the candidate reads, nothing dropped or substituted."""
    _, counselor_auth = counselor_auth
    client.post("/api/voyage/c/tok-conseiller/validate", headers=counselor_auth)
    res = client.get("/api/voyage/portrait", headers=auth)
    assert res.status_code == 200
    assert res.get_json()["portrait"]["sections"] == {k: f"texte {k}" for k in PORTRAIT_KEYS}


def test_an_edit_is_still_allowed_after_validation(client, sheet, counselor_auth):
    """A correction made during the restitution session must not require
    un-validating the portrait in front of the person."""
    _, counselor_auth = counselor_auth
    client.post("/api/voyage/c/tok-conseiller/validate", headers=counselor_auth)
    res = client.put("/api/voyage/c/tok-conseiller/portrait",
                     json={"sections": _sections()}, headers=counselor_auth)
    assert res.status_code == 200
    assert res.get_json()["portrait"]["status"] == "validated"


# ── private notes ────────────────────────────────────────────────────────────

def test_notes_start_empty_and_upsert(client, sheet, counselor_auth):
    _, counselor_auth = counselor_auth
    assert client.get("/api/voyage/c/tok-conseiller/notes",
                      headers=counselor_auth).get_json()["note"] is None

    res = client.put("/api/voyage/c/tok-conseiller/notes",
                     json={"body": "à revoir en RDV 2"}, headers=counselor_auth)
    assert res.status_code == 200
    assert res.get_json()["note"]["body"] == "à revoir en RDV 2"

    res = client.put("/api/voyage/c/tok-conseiller/notes",
                     json={"body": ""}, headers=counselor_auth)
    assert res.get_json()["note"]["body"] == ""
    assert VoyageNote.query.count() == 1


def test_a_note_belongs_to_the_counselor_who_wrote_it(client, sheet, counselor_auth, app):
    """Not just that two rows exist: each counselor's own GET must return
    their own text, never the colleague's."""
    _, counselor_auth = counselor_auth
    client.put("/api/voyage/c/tok-conseiller/notes",
               json={"body": "note A"}, headers=counselor_auth)
    other = _headers(_user("conseiller-2@test.fr", role="counselor"))
    assert client.get("/api/voyage/c/tok-conseiller/notes",
                      headers=other).get_json()["note"] is None
    client.put("/api/voyage/c/tok-conseiller/notes", json={"body": "note B"}, headers=other)
    assert VoyageNote.query.count() == 2

    res_1 = client.get("/api/voyage/c/tok-conseiller/notes", headers=counselor_auth)
    assert res_1.get_json()["note"]["body"] == "note A"
    res_2 = client.get("/api/voyage/c/tok-conseiller/notes", headers=other)
    assert res_2.get_json()["note"]["body"] == "note B"


def test_a_candidate_cannot_read_counselor_notes(client, sheet, auth):
    assert client.get("/api/voyage/c/tok-conseiller/notes", headers=auth).status_code == 403


def test_a_candidate_cannot_write_counselor_notes(client, sheet, auth):
    """The role gate applies to the write side too, not only the read side."""
    res = client.put("/api/voyage/c/tok-conseiller/notes",
                     json={"body": "je ne devrais pas pouvoir écrire ceci"}, headers=auth)
    assert res.status_code == 403
    assert VoyageNote.query.count() == 0


def test_a_malformed_note_body_is_refused_without_destroying_the_existing_note(
        client, sheet, counselor_auth):
    """Task 12 review, finding 1: coercing a malformed body to "" wiped an
    existing note under a 200 — a rejected input became destroyed data
    reported as success. A JSON array, a bare number, a bare string, a
    non-string "body" field, and — final-review finding 3 — a dict with no
    "body" key at all (data.get("body", "") made an absent key
    indistinguishable from an explicit "") must all be refused outright, and
    the note already on file must survive every one of them untouched."""
    _, counselor_auth = counselor_auth
    res = client.put("/api/voyage/c/tok-conseiller/notes",
                     json={"body": "note importante"}, headers=counselor_auth)
    assert res.status_code == 200
    assert res.get_json()["note"]["body"] == "note importante"

    for body in ([1, 2, 3], 42, "a string", {"body": 42}, {}, {"autre": "x"}):
        res = client.put("/api/voyage/c/tok-conseiller/notes", json=body, headers=counselor_auth)
        assert res.status_code == 400
        assert res.get_json()["error"] == "Note invalide."

    res = client.get("/api/voyage/c/tok-conseiller/notes", headers=counselor_auth)
    assert res.get_json()["note"]["body"] == "note importante"


def test_an_empty_string_body_still_clears_the_note(client, sheet, counselor_auth):
    """The rejection in the test above must not have swallowed the one
    legitimate way to clear a note: an explicit "" (contract § E15)."""
    _, counselor_auth = counselor_auth
    client.put("/api/voyage/c/tok-conseiller/notes",
               json={"body": "à effacer"}, headers=counselor_auth)
    res = client.put("/api/voyage/c/tok-conseiller/notes",
                     json={"body": ""}, headers=counselor_auth)
    assert res.status_code == 200
    assert res.get_json()["note"]["body"] == ""


def test_an_unknown_token_404s_every_counselor_route(client, counselor_auth):
    """The 404 guard is not just on the sheet's GET — every one of the five
    counselor handlers resolves the token first and must refuse the same way
    for a token nobody holds."""
    _, counselor_auth = counselor_auth
    msg = {"error": "Voyage introuvable."}
    assert client.put("/api/voyage/c/nope/portrait", json={"sections": _sections()},
                      headers=counselor_auth).get_json() == msg
    assert client.post("/api/voyage/c/nope/portrait/regenerate",
                       headers=counselor_auth).get_json() == msg
    assert client.post("/api/voyage/c/nope/validate", headers=counselor_auth).get_json() == msg
    assert client.get("/api/voyage/c/nope/notes", headers=counselor_auth).get_json() == msg
    assert client.put("/api/voyage/c/nope/notes", json={"body": "x"},
                      headers=counselor_auth).get_json() == msg


# ── an errored portrait must not be a dead end ───────────────────────────────


def _to_error(voyage, message="upstream timeout"):
    """Put the sheet's portrait in the state the reaper and a failed run leave."""
    voyage.portrait = {**(voyage.portrait or {}), "error": message}
    voyage.portrait_status = "error"
    _db.session.commit()


def test_a_counselor_can_regenerate_a_portrait_that_errored(client, sheet, counselor_auth):
    """Nothing else in the backend moves a row out of 'error': edit and validate
    both 409, S5 cannot be completed twice, and the startup reaper *creates*
    error rows from runs a restart orphaned. Without this, one transient
    upstream failure destroys a finished six-session voyage for good.
    """
    _, counselor_auth = counselor_auth
    _to_error(sheet)

    with patch("app.routes.voyage._spawn_portrait") as spawn:
        res = client.post("/api/voyage/c/tok-conseiller/portrait/regenerate",
                          headers=counselor_auth)

    assert res.status_code == 202
    spawn.assert_called_once()
    assert res.get_json()["portrait"]["status"] == "generating"
    _db.session.expire_all()
    assert _db.session.get(Voyage, sheet.id).portrait_status == "generating"


def test_a_validated_portrait_still_refuses_to_regenerate(client, sheet, counselor_auth):
    """The widening is 'draft or error', not 'anything'. A validated portrait
    has been restituted and must not change under the person's feet."""
    _, counselor_auth = counselor_auth
    sheet.portrait_status = "validated"
    _db.session.commit()

    res = client.post("/api/voyage/c/tok-conseiller/portrait/regenerate",
                      headers=counselor_auth)
    assert res.status_code == 409


def test_the_failure_reason_reaches_the_counselor_who_must_act_on_it(client, sheet,
                                                                     counselor_auth):
    """A failure the counselor cannot see is a failure they cannot act on."""
    _, counselor_auth = counselor_auth
    _to_error(sheet, "Aucun prompt actif pour le slot voyage_portrait.")

    body = client.get("/api/voyage/c/tok-conseiller",
                      headers=counselor_auth).get_json()["voyage"]["portrait"]
    assert body["status"] == "error"
    assert body["error"] == "Aucun prompt actif pour le slot voyage_portrait."


def test_a_healthy_draft_carries_no_error_key(client, sheet, counselor_auth):
    """The contract pins the healthy shape at exactly five keys; `error` is
    added only on an error row, never as a null beside a good draft."""
    _, counselor_auth = counselor_auth
    body = client.get("/api/voyage/c/tok-conseiller",
                      headers=counselor_auth).get_json()["voyage"]["portrait"]
    assert set(body) == {"status", "sections", "flags", "edited", "validated_at"}

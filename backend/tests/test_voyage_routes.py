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


# ── GET / PUT /api/voyage/responses ──────────────────────────────────────────

def _open_voyage(client, auth):
    client.post("/api/voyage", json={"consent": True, "age_attested": True}, headers=auth)
    return Voyage.query.one()


def test_responses_start_empty_and_come_back_whole(client, auth):
    _open_voyage(client, auth)
    res = client.get("/api/voyage/responses", headers=auth)
    assert res.status_code == 200
    assert res.get_json()["responses"] == {"answers": {}, "billets": {}}


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
    voyage.counselor_code_id = "code-1"
    _db.session.commit()
    res = client.post("/api/voyage/sessions/1/complete", headers=auth)
    assert res.status_code == 403
    assert res.get_json()["error"] == LOCK_PROFILE


def test_sessions_must_be_completed_in_order(client, auth, candidate):
    _open_voyage(client, auth)
    _play_session_zero(client, auth)
    voyage = Voyage.query.one()
    voyage.counselor_code_id = "code-1"
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
    voyage.counselor_code_id = "code-1"
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
    voyage.counselor_code_id = "code-1"
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
    sections, never the neighbour's."""
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

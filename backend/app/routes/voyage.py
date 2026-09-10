"""Le voyage — the candidate's six sessions and the counselor's sheet.

Two audiences, two access rules, one blueprint:

  * candidate handlers are owner-scoped. They resolve the caller's own current
    voyage and never take an id from the client, so there is nothing to
    enumerate and no ownership check to forget.
  * counselor handlers need the counselor/admin role **and** the share token.
    That is deliberately stricter than /api/c/<token> for analyses: the
    synthesis sheet is a psychometric read-out, so a leaked link alone must
    not open it (spec § Security).

Session locking is enforced here and not only in the UI — see
models.voyage.session_lock: S0 needs the voyage to exist, S1-S5 need a
counselor code and a Profil de base with prénom + tranche d'âge, and every
session needs the one before it.
"""
from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from ..extensions import db
from ..models.profile import Profile
from ..models.voyage import (
    CONSENT_VERSION,
    STATUS_EN_COURS,
    Voyage,
    session_lock,
)
from ..services.voyage import bank

voyage_bp = Blueprint("voyage", __name__)

# The API's fixed French strings. app.url_map.strict_slashes is False globally,
# so "" also answers "/" — do not add per-route slash handling.
NO_VOYAGE = "Aucun voyage en cours."


def _current() -> Voyage | None:
    """The caller's own voyage: the open one, else the last one played."""
    return Voyage.current_for(get_jwt_identity())


def _profile() -> Profile | None:
    return Profile.query.filter_by(user_id=get_jwt_identity()).first()


# ── candidate ────────────────────────────────────────────────────────────────

@voyage_bp.get("/bank")
@jwt_required()
def get_bank():
    """The question bank, text only.

    bank.public() strips every scoring key at every depth. The mapping from an
    option to a trait is the product and the counselor manual is confidential,
    so it never crosses this line.
    """
    return jsonify({"bank": bank.public()}), 200


@voyage_bp.get("")
@jwt_required()
def get_voyage():
    voyage = _current()
    return jsonify({"voyage": voyage.to_dict() if voyage else None}), 200


@voyage_bp.post("")
@jwt_required()
def create_voyage():
    """Start a voyage. Both boxes are mandatory and both are recorded.

    Consent is a separate record from the profile's: a psychometric profile is
    not covered by consent given for a CV analysis. The age attestation is the
    French digital-consent floor; under-15 parental consent is out of scope for
    v1 (spec decision 13).
    """
    data = request.get_json(silent=True)
    data = data if isinstance(data, dict) else {}
    errors = []
    if data.get("consent") is not True:
        errors.append("Le consentement est requis.")
    if data.get("age_attested") is not True:
        errors.append("Vous devez attester avoir 15 ans ou plus.")
    if errors:
        return jsonify({"errors": errors}), 400

    user_id = get_jwt_identity()
    if Voyage.open_for(user_id) is not None:
        return jsonify({"error": "Un voyage est déjà en cours."}), 409

    voyage = Voyage(
        user_id=user_id,
        status=STATUS_EN_COURS,
        sessions_completed=[],
        consent_at=datetime.utcnow(),
        consent_version=CONSENT_VERSION,
        age_attested=True,
        scoring_version=bank.SCORING_VERSION,
    )
    db.session.add(voyage)
    db.session.commit()
    return jsonify({"voyage": voyage.to_dict()}), 201


@voyage_bp.delete("")
@jwt_required()
def delete_voyage():
    """RGPD erasure, independent of the profile in both directions.

    Not a 404 when there is nothing: the person asked for nothing to be left,
    and nothing is left (mirrors delete_profile).
    """
    voyage = _current()
    if voyage is None:
        return jsonify({"message": "Aucun voyage à supprimer."}), 200
    db.session.delete(voyage)
    db.session.commit()
    return jsonify({"message": "Voyage supprimé."}), 200


def _session_of(item_id: str) -> str:
    """"S0-01" -> "0", "S3-7" -> "3". Every bank id is S<n>-<k>."""
    return item_id[1]


@voyage_bp.get("/responses")
@jwt_required()
def get_responses():
    """The person's own answers, for resuming a session or re-rendering it."""
    voyage = _current()
    if voyage is None:
        return jsonify({"error": NO_VOYAGE}), 404
    return jsonify({"responses": voyage.responses}), 200


@voyage_bp.put("/responses")
@jwt_required()
def put_responses():
    """Merge answers and exit tickets into the voyage.

    Merge, not replace: the player saves on every « Suivant », so a lost
    connection costs one scene rather than a session. Unknown ids are dropped
    silently — a client one deploy behind must not lose a whole save over an
    item that moved — but a known id carrying a value the bank rejects is a
    400, because that means the two have genuinely drifted.
    """
    voyage = _current()
    if voyage is None:
        return jsonify({"error": NO_VOYAGE}), 404

    data = request.get_json(silent=True)
    if data is not None and not isinstance(data, dict):
        # A body that parsed as valid JSON but the wrong top-level shape (an
        # array, a bare string, a number) is refused outright — treating it
        # like {} here would hide a client bug behind a silent no-op. An
        # absent or unparseable body stays a no-op (data is None -> {}),
        # matching the "empty PUT" contract the tests rely on.
        return jsonify({"error": "Corps de requête invalide."}), 400
    data = data or {}
    raw_answers = data.get("answers")
    raw_billets = data.get("billets")
    answers = raw_answers if isinstance(raw_answers, dict) else {}
    billets = raw_billets if isinstance(raw_billets, dict) else {}

    known = {i: v for i, v in answers.items() if bank.item(i) is not None}

    # Locks are checked over every session the request touches, before any
    # merge — a refusal must leave the row exactly as it was.
    touched = {_session_of(i) for i in known}
    touched |= {n for n in billets if n in bank.SESSION_IDS}
    profile = _profile()
    for n in sorted(touched):
        lock = session_lock(voyage, profile, n)
        if lock:
            return jsonify({"error": lock}), 403

    invalid = [
        f"Réponse invalide pour {i}."
        for i, value in sorted(known.items())
        if not bank.validate_answer(i, value)
    ]
    if invalid:
        return jsonify({"errors": invalid}), 400

    merged = voyage.responses
    merged["answers"].update(known)
    for n, fields in billets.items():
        if n not in bank.SESSION_IDS or not isinstance(fields, dict):
            continue
        allowed = set(bank.billet_keys(n))
        target = dict(merged["billets"].get(n) or {})
        for key, value in fields.items():
            if key in allowed:
                target[key] = "" if value is None else str(value)
        merged["billets"][n] = target

    voyage.responses = merged
    db.session.commit()
    return jsonify({"responses": voyage.responses}), 200

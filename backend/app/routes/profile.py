"""Profil de base — read, upsert, erase.

The OETH invariant runs through this whole file: ticking the box must change
nothing observable. Same response shape, same status code, same rows touched,
whether or not it is set. See `_upsert_sensitive`.
"""
from datetime import datetime

from flask import Blueprint, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required

from ..extensions import db
from ..models.profile import (
    AGE_BRACKETS,
    RECONVERSION_SCOPES,
    SEARCH_RADIUS,
    SITUATIONS,
    Profile,
    SensitiveProfile,
    normalize_conditions,
)
from ..utils.request_body import json_object

profile_bp = Blueprint("profile", __name__)

CONSENT_VERSION = "v1.2"

# (field, allowed values) — anything outside the set is rejected rather than
# silently coerced, because these drive routing (parcours 3 youth schemes,
# the Académie des Ori variant) and a wrong value is not a cosmetic issue.
_ENUMS = {
    "rayon": SEARCH_RADIUS,
    "tranche_age": AGE_BRACKETS,
    "situation": SITUATIONS,
    "reconversion_scope": RECONVERSION_SCOPES,
}

_TEXT_FIELDS = (
    "prenom", "nom", "ville",
    "projet", "projet_document", "contraintes_pratiques",
)


def _validate(data: dict) -> list[str]:
    errors = []
    for field, allowed in _ENUMS.items():
        value = data.get(field)
        if value in (None, ""):
            continue
        if value not in allowed:
            errors.append(f"Valeur invalide pour {field}.")

    # The sub-question only exists when the situation is a reconversion.
    if data.get("reconversion_scope") and data.get("situation") != "en_reconversion":
        errors.append("reconversion_scope ne s'applique qu'à une reconversion.")

    return errors


def _upsert_sensitive(profile: Profile, data: dict) -> None:
    """Write bloc 5 and the OETH flag.

    The row is created unconditionally — including when OETH is false and
    bloc 5 is empty. If it only existed for people who ticked the box, the
    mere presence of the row would leak the flag to anything that can read
    the table, which is exactly what the separate-storage rule is meant to
    prevent.
    """
    sensitive = profile.sensitive
    if sensitive is None:
        sensitive = SensitiveProfile(profile_id=profile.id)
        db.session.add(sensitive)
        profile.sensitive = sensitive

    if "conditions" in data:
        sensitive.conditions = normalize_conditions(data.get("conditions"))
    if "oeth" in data:
        sensitive.oeth = data.get("oeth")


@profile_bp.get("")
@jwt_required()
def get_profile():
    profile = Profile.query.filter_by(user_id=get_jwt_identity()).first()
    if profile is None:
        return jsonify({"profile": None}), 200
    return jsonify({"profile": profile.to_dict()}), 200


@profile_bp.get("/conditions")
@jwt_required()
def get_conditions():
    """The sensitive half, for re-rendering the form its owner already filled.

    Deliberately a separate endpoint from GET /profile: the ordinary payload
    must never carry this, so it cannot leak by accident into a log line, an
    admin view, or a PDF that renders the profile.

    The OETH rule is "ticking it triggers nothing visible" — no new field, no
    re-layout, no change of flow. Handing someone back their own stored answer
    so the checkbox renders as they left it is persistence, not a reaction.
    Dropping it would be worse than a leak: a second save would silently clear
    a status that governs the person's rights.
    """
    profile = Profile.query.filter_by(user_id=get_jwt_identity()).first()
    if profile is None or profile.sensitive is None:
        return jsonify({"conditions": {}, "oeth": False}), 200
    return jsonify({
        "conditions": profile.sensitive.conditions,
        "oeth": profile.sensitive.oeth,
    }), 200


@profile_bp.put("")
@jwt_required()
def upsert_profile():
    user_id = get_jwt_identity()
    data = json_object()

    errors = _validate(data)
    if errors:
        return jsonify({"errors": errors}), 400

    profile = Profile.query.filter_by(user_id=user_id).first()
    creating = profile is None
    if creating:
        profile = Profile(user_id=user_id)
        db.session.add(profile)

    # Consent is mandatory before anything is stored (CDC §3.1: the submit
    # button stays inactive until the box is ticked — this is the server-side
    # half of that rule).
    if data.get("consent") is True:
        profile.consent_at = datetime.utcnow()
        profile.consent_version = CONSENT_VERSION
    elif creating:
        return jsonify({"errors": ["Le consentement est requis."]}), 400

    for field in _TEXT_FIELDS:
        if field in data:
            value = data.get(field)
            setattr(profile, field, (value or "").strip() or None)

    for field in _ENUMS:
        if field in data:
            setattr(profile, field, data.get(field) or None)

    # A situation that is no longer a reconversion must not keep a stale scope.
    if profile.situation != "en_reconversion":
        profile.reconversion_scope = None

    # NOM is displayed in caps throughout the report.
    if profile.nom:
        profile.nom = profile.nom.upper()

    db.session.flush()  # profile.id, for the sensitive row's FK
    _upsert_sensitive(profile, data)
    db.session.commit()

    return jsonify({"profile": profile.to_dict()}), 201 if creating else 200


@profile_bp.delete("")
@jwt_required()
def delete_profile():
    """RGPD erasure. Cascades to the sensitive row."""
    profile = Profile.query.filter_by(user_id=get_jwt_identity()).first()
    if profile is None:
        return jsonify({"message": "Aucun profil à supprimer."}), 200
    db.session.delete(profile)
    db.session.commit()
    return jsonify({"message": "Profil supprimé."}), 200

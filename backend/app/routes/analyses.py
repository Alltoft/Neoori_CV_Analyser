import os
import re

from flask import Blueprint, current_app, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from ..extensions import db
from ..models.analysis import Analysis
from ..models.counselor_code import CounselorCode
from ..models.price_feedback import BUCKETS, PriceFeedback
from ..models.profile import Profile, prompt_context
from ..utils.tokens import generate_share_token
from ..utils.request_body import json_object, text_field
from ..services import section_registry as registry
from ..services import tiers
from ..services.anthropic_service import start_analysis
from ..services.unlock_service import unlock_analysis

analyses_bp = Blueprint("analyses", __name__)

# ── TEMPORARY: force every analysis to one tier ──────────────────────────────
# While the PM reviews report *content*, the free tier's three sections aren't
# what needs judging — so every analysis runs paid until they're done.
#
# To restore normal behaviour: change the default below to "" (or set
# FORCE_ANALYSIS_TIER="" on Render). The paywall, the unlock flow and the
# Premium checkout are untouched — this only decides what a *new* analysis
# generates.
_FORCE_TIER = tiers.normalize(os.getenv("FORCE_ANALYSIS_TIER", "paid")) \
    if os.getenv("FORCE_ANALYSIS_TIER", "paid") else None

# Parcours 1 splits in two (Parcours doc §4). Chemin A is an actual job ad,
# pasted or uploaded — the report compares the CV against it point by point.
# Chemin B is the person's own description of a target, which the report has to
# announce as such: no sector lookup runs at launch (PM ruling), so nothing in
# it is sourced and the opening note says so.
CHEMIN_OFFRE = "A"
CHEMIN_DESCRIPTION = "B"

# The doc puts the floor for a described target at 20 characters. A job ad that
# short is a paste that went wrong, so chemin A keeps the original 50.
CIBLE_MIN = {CHEMIN_OFFRE: 50, CHEMIN_DESCRIPTION: 20}


def _normalize_chemin(value) -> str:
    """Coerce to a chemin, defaulting to the offer.

    Analyses written before the chemin was carried have no value, and their
    behaviour was chemin A — direct analysis, no framing note.
    """
    if str(value or "").strip().upper() == CHEMIN_DESCRIPTION:
        return CHEMIN_DESCRIPTION
    return CHEMIN_OFFRE


@analyses_bp.post("/")
def create_analysis():
    user_id = _optional_user_id()
    data = json_object()
    inputs = dict(data.get("inputs", {}))
    # normalize() maps the legacy 'A'/'B' codes onto parcours ids and falls
    # back to parcours 1 for anything unrecognised.
    path = registry.normalize(inputs.get("_path"))
    inputs["_path"] = path
    # Only parcours 1 has chemins; carrying the key elsewhere would be noise in
    # the stored inputs and in every prompt built from them.
    if path == "1":
        inputs["_chemin"] = _normalize_chemin(inputs.get("_chemin"))

    if _FORCE_TIER:
        # TEMPORARY — see _FORCE_TIER above. Delete the default to restore
        # normal tier selection.
        inputs["_tier"] = _FORCE_TIER
    elif path == "3":
        # Parcours 3 runs on the paid model for everyone — it serves the
        # populations the free tier exists to reach.
        inputs["_tier"] = tiers.PAID
    else:
        # normalize() accepts the legacy "haiku"/"sonnet" nicknames and
        # falls back to free for anything unrecognised.
        inputs["_tier"] = tiers.normalize(data.get("tier"))

    errors = VALIDATORS[path](inputs)
    if errors:
        return jsonify({"errors": errors}), 400

    # Fold in the Profil de base so the parcours forms never re-ask what the
    # profile already knows, and pre-shape bloc 5 into the three lists the
    # report may use — the raw answers never reach the model.
    _merge_profile(inputs, user_id)

    analysis = Analysis(
        user_id=user_id,
        inputs=inputs,
        status="queued",
        share_token=generate_share_token(),
    )
    db.session.add(analysis)
    db.session.commit()

    # Hand the slow Anthropic call to a background thread so the HTTP
    # response returns immediately. The frontend polls GET /analyses/<id>
    # for status — avoids edge-proxy timeouts on long Sonnet generations.
    start_analysis(analysis.id, current_app._get_current_object())

    return jsonify({"analysis": analysis.to_dict()}), 201


@analyses_bp.post("/draft")
@jwt_required()
def save_draft():
    """Create or update a draft. Auth required — anonymous drafts would be
    orphaned (no user_id) and never visible in the user's space."""
    user_id = get_jwt_identity()
    data = json_object()
    inputs = data.get("inputs", {})
    draft_id = data.get("draft_id")

    if draft_id:
        analysis = Analysis.query.filter_by(
            id=draft_id, user_id=user_id, status="draft"
        ).first()
        if analysis:
            analysis.inputs = inputs
            db.session.commit()
            return jsonify({"analysis": analysis.to_dict()}), 200

    analysis = Analysis(
        user_id=user_id,
        inputs=inputs,
        status="draft",
    )
    db.session.add(analysis)
    db.session.commit()
    return jsonify({"analysis": analysis.to_dict()}), 201


@analyses_bp.get("/")
@jwt_required()
def list_analyses():
    user_id = get_jwt_identity()
    analyses = (
        Analysis.query
        .filter_by(user_id=user_id)
        .order_by(Analysis.created_at.desc())
        .all()
    )
    return jsonify({"analyses": [a.to_dict() for a in analyses]}), 200


@analyses_bp.get("/<analysis_id>")
def get_analysis(analysis_id):
    """Poll status / fetch a result.

    Deliberately not @jwt_required: the anonymous flow (no account yet) has to
    poll its own analysis, and the phase-1 rebuild is what makes accounts
    mandatory. But an analysis that *has* an owner is readable only by that
    owner — previously any caller could read any analysis, inputs included:
    CV text, name, location, and the health context parcours 3 collects.
    """
    analysis = Analysis.query.get_or_404(analysis_id)
    if not _may_access(analysis):
        return jsonify({"error": "Accès non autorisé."}), 403
    return jsonify({"analysis": analysis.to_dict()}), 200


@analyses_bp.post("/<analysis_id>/unlock")
def unlock_with_code(analysis_id):
    """Redeem a counselor code: free paid-tier regeneration (Cap Emploi /
    France Travail beneficiaries). Payment unlocks go through /api/payments."""
    analysis = Analysis.query.get_or_404(analysis_id)
    if not _may_access(analysis):
        return jsonify({"error": "Accès non autorisé."}), 403
    data = json_object()

    # Accept "ABCD1234", "abcd 1234", "ABCD-1234"… — codes are 8 alnum chars
    raw = text_field(data, "code")
    code_str = re.sub(r"[^A-Za-z0-9]", "", raw).upper()
    if not code_str:
        return jsonify({"error": "Code requis."}), 400

    code = CounselorCode.query.filter_by(code=code_str).first()
    if not code or not code.is_active:
        return jsonify({"error": "Code invalide ou désactivé."}), 400

    ok, reason = unlock_analysis(analysis, method="code")
    if not ok:
        return jsonify({"error": reason}), 409

    code.uses_count += 1
    db.session.commit()
    return jsonify({"analysis": analysis.to_dict()}), 200


@analyses_bp.post("/<analysis_id>/price-feedback")
def submit_price_feedback(analysis_id):
    """Willingness-to-pay probe, shown after a free report.

    Idempotent per analysis: re-answering replaces the previous answer rather
    than stacking, so one person can't skew the distribution by resubmitting.
    """
    analysis = Analysis.query.get_or_404(analysis_id)
    if not _may_access(analysis):
        return jsonify({"error": "Accès non autorisé."}), 403

    data = json_object()
    bucket = text_field(data, "bucket")
    if bucket not in BUCKETS:
        return jsonify({"error": "Réponse invalide."}), 400

    row = PriceFeedback.query.filter_by(analysis_id=analysis_id).first()
    if row is None:
        row = PriceFeedback(analysis_id=analysis_id, bucket=bucket)
        db.session.add(row)
    row.bucket = bucket
    if "useful" in data:
        row.useful = bool(data.get("useful"))
    db.session.commit()
    return jsonify({"feedback": row.to_dict()}), 200


@analyses_bp.delete("/<analysis_id>")
def delete_analysis(analysis_id):
    analysis = Analysis.query.get_or_404(analysis_id)
    if not _may_access(analysis):
        return jsonify({"error": "Accès non autorisé."}), 403

    db.session.delete(analysis)
    db.session.commit()
    return jsonify({"message": "Analyse supprimée."}), 200


# ── helpers ───────────────────────────────────────────────────────────────────

def _merge_profile(inputs: dict, user_id: str | None) -> None:
    """Copy the Profil de base into this analysis's inputs.

    The ordinary fields are copied so the analysis stays readable on its own
    (a later profile edit must not silently rewrite an already-delivered
    report). Bloc 5 is reduced to prompt_context() first, and the OETH flag
    becomes a plain boolean — neither the raw condition answers nor the status
    itself is ever stored on the analysis.
    """
    if not user_id:
        return
    profile = Profile.query.filter_by(user_id=user_id).first()
    if profile is None:
        return

    for field in ("prenom", "nom", "ville", "rayon", "tranche_age",
                  "situation", "reconversion_scope", "projet",
                  "contraintes_pratiques"):
        inputs.setdefault(field, getattr(profile, field, None))

    sensitive = profile.sensitive
    if sensitive is not None:
        inputs["_conditions"] = prompt_context(sensitive.conditions)
        inputs["_oeth"] = sensitive.oeth


def _may_access(analysis: Analysis) -> bool:
    """Owner-only once an analysis has an owner.

    An ownerless (anonymous) analysis stays reachable by anyone holding its
    id — the UUID4 *is* the capability there, and there is no account to check
    against. Phase 1 makes accounts mandatory, at which point the ownerless
    branch is dead code and this collapses to a plain ownership test.
    """
    if analysis.user_id is None:
        return True
    return analysis.user_id == _optional_user_id()


def _optional_user_id() -> str | None:
    """Return current user id if a valid JWT is present, else None."""
    try:
        verify_jwt_in_request(optional=True)
        return get_jwt_identity()
    except Exception:
        return None


def _validate_inputs(inputs: dict) -> list[str]:
    """Parcours 1 — a CV and a target, and nothing else.

    Identity, age, location, situation and mobility used to be required here.
    They are fields of the Profil de base, folded in by _merge_profile, and
    `type_mobilite` no longer exists at all — the CDC v1.2 profile merged it
    into `situation`. Requiring them meant a form that asked twice and a
    validator that could reject an analysis over a field the data model had
    already deleted.
    """
    errors = []

    has_cv = (inputs.get("cv_text") or "").strip()
    if len(has_cv) < 200:
        errors.append("CV trop court (minimum 200 caractères).")

    minimum = CIBLE_MIN[_normalize_chemin(inputs.get("_chemin"))]
    cible = (inputs.get("cible_visee") or "").strip()
    if len(cible) < minimum:
        errors.append(f"Cible visée trop courte (minimum {minimum} caractères).")

    return errors


# ── per-parcours validation ──────────────────────────────────────────────────
# Each parcours asks for different things. Keeping the rules in one table
# rather than nested branches means adding a parcours is a new entry, not a
# new `if` inside three functions.

def _missing(inputs: dict, field: str, label: str, minimum: int = 1) -> str | None:
    value = (inputs.get(field) or "").strip()
    if len(value) < minimum:
        if minimum > 1:
            return f"{label} — réponse trop courte ({minimum} caractères minimum)."
        return f"{label} — réponse requise."
    return None


def _validate_inputs_p2(inputs: dict) -> list[str]:
    """Parcours 2 — a CV (or a raw list of experiences) plus 3 questions.

    Three, not four: constraints live in bloc 4 of the profile and health is
    covered for everyone by bloc 5, so the fourth question was re-asking what
    the profile already knew.
    """
    errors = []
    if len((inputs.get("cv_text") or "").strip()) < 200:
        errors.append("CV ou liste d'expériences trop courte (200 caractères minimum).")
    for field, label in (
        ("satisfaction", "Ce qui vous a donné le plus de satisfaction"),
        ("refus", "Ce que vous ne voulez plus faire"),
        ("raison_changement", "La raison principale de votre changement"),
    ):
        if err := _missing(inputs, field, label, minimum=20):
            errors.append(err)
    return errors


def _validate_inputs_p3(inputs: dict) -> list[str]:
    """Parcours 3 — no CV. The five life questions are the input."""
    errors = []
    for field, label in (
        ("experiences", "Ce que vous avez fait jusqu'à présent"),
        ("aime_faire", "Ce que vous aimez faire"),
        ("refus", "Ce que vous ne voulez pas ou ne pouvez pas faire"),
        ("contraintes", "Vos contraintes pratiques"),
        ("bon_travail", "Ce qu'est un bon travail pour vous"),
    ):
        # Deliberately lower than parcours 2: this parcours exists for people
        # who don't have a CV, and a long-answer requirement is exactly the
        # kind of barrier it is meant to remove.
        if err := _missing(inputs, field, label, minimum=10):
            errors.append(err)
    return errors


VALIDATORS = {
    "1": _validate_inputs,
    "2": _validate_inputs_p2,
    "3": _validate_inputs_p3,
}

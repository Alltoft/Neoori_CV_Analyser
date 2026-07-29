import re

from flask import Blueprint, current_app, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from ..extensions import db
from ..models.analysis import Analysis
from ..models.counselor_code import CounselorCode
from ..utils.tokens import generate_share_token
from ..services import section_registry as registry
from ..services.anthropic_service import start_analysis
from ..services.unlock_service import unlock_analysis

analyses_bp = Blueprint("analyses", __name__)

_REQUIRED_INPUTS = [
    "cible_visee", "prenom", "nom", "tranche_age",
    "localisation", "situation_actuelle", "type_mobilite",
]


@analyses_bp.post("/")
def create_analysis():
    user_id = _optional_user_id()
    data = request.get_json(silent=True) or {}
    inputs = dict(data.get("inputs", {}))
    # normalize() maps the legacy 'A'/'B' codes onto parcours ids and falls
    # back to parcours 1 for anything unrecognised.
    path = registry.normalize(inputs.get("_path"))
    inputs["_path"] = path

    if path == "2":
        # Parcours 2's questionnaire ships in phase 2 of the CDC v1.2 rebuild.
        return jsonify({"errors": ["Ce parcours n'est pas encore disponible."]}), 400

    if path == "3":
        # Parcours 3 is forced to Sonnet (free for vulnerable populations).
        inputs["_tier"] = "sonnet"
        errors = _validate_inputs_b(inputs)
    else:
        tier = data.get("tier", "haiku")
        if tier not in ("haiku", "sonnet"):
            tier = "haiku"
        inputs["_tier"] = tier
        errors = _validate_inputs(inputs)
    if errors:
        return jsonify({"errors": errors}), 400

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
    data = request.get_json(silent=True) or {}
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
    analysis = Analysis.query.get_or_404(analysis_id)
    return jsonify({"analysis": analysis.to_dict()}), 200


@analyses_bp.post("/<analysis_id>/unlock")
def unlock_with_code(analysis_id):
    """Redeem a counselor code: free paid-tier regeneration (Cap Emploi /
    France Travail beneficiaries). Payment unlocks go through /api/payments."""
    analysis = Analysis.query.get_or_404(analysis_id)
    data = request.get_json(silent=True) or {}

    # Accept "ABCD1234", "abcd 1234", "ABCD-1234"… — codes are 8 alnum chars
    raw = (data.get("code") or "").strip()
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


@analyses_bp.delete("/<analysis_id>")
def delete_analysis(analysis_id):
    analysis = Analysis.query.get_or_404(analysis_id)

    # Allow delete if anonymous analysis (no owner) or if logged-in user owns it
    user_id = _optional_user_id()
    if analysis.user_id is not None and analysis.user_id != user_id:
        return jsonify({"error": "Accès non autorisé."}), 403

    db.session.delete(analysis)
    db.session.commit()
    return jsonify({"message": "Analyse supprimée."}), 200


# ── helpers ───────────────────────────────────────────────────────────────────

def _optional_user_id() -> str | None:
    """Return current user id if a valid JWT is present, else None."""
    try:
        verify_jwt_in_request(optional=True)
        return get_jwt_identity()
    except Exception:
        return None


def _validate_inputs(inputs: dict) -> list[str]:
    errors = []

    has_cv = (inputs.get("cv_text") or "").strip()
    if len(has_cv) < 200:
        errors.append("CV trop court (minimum 200 caractères).")

    cible = (inputs.get("cible_visee") or "").strip()
    if len(cible) < 50:
        errors.append("Cible visée trop courte (minimum 50 caractères).")

    for field in _REQUIRED_INPUTS:
        val = inputs.get(field)
        if field == "type_mobilite":
            if not (isinstance(val, list) and any((v or "").strip() for v in val)):
                errors.append(f"Champ manquant : {field}.")
        elif not (val or "").strip():
            errors.append(f"Champ manquant : {field}.")

    return errors


_SUB_PROFILES_B = ("b1", "b2", "b3")


def _validate_inputs_b(inputs: dict) -> list[str]:
    errors = []
    sub = (inputs.get("_sub_profile") or "").lower()
    if sub not in _SUB_PROFILES_B:
        errors.append("Sous-profil invalide (attendu b1, b2 ou b3).")
    if not (inputs.get("nom") or "").strip():
        errors.append("Prénom et nom requis.")

    def _nonempty_list(key: str) -> bool:
        v = inputs.get(key)
        return isinstance(v, list) and any((str(x).strip() for x in v))

    if not _nonempty_list("aime"):
        errors.append("Sélectionnez au moins un choix : ce que vous aimez faire.")
    if not _nonempty_list("competent"):
        errors.append("Sélectionnez au moins un choix : situations de compétence.")

    if sub == "b2":
        if not (inputs.get("pause_activite") or "").strip():
            errors.append("Activité pendant la pause requise.")
    if sub == "b3":
        if not (inputs.get("accompagnement") or "").strip():
            errors.append("Accompagnement requis.")

    return errors

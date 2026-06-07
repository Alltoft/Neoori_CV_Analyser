from flask import Blueprint, current_app, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from ..extensions import db
from ..models.analysis import Analysis
from ..utils.tokens import generate_share_token
from ..services.anthropic_service import start_analysis

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
    path = (inputs.get("_path") or "A").upper()
    if path not in ("A", "B"):
        path = "A"
    inputs["_path"] = path

    if path == "B":
        # Chemin B is forced to Sonnet (free for vulnerable populations).
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
def save_draft():
    user_id = _optional_user_id()
    data = request.get_json(silent=True) or {}
    inputs = data.get("inputs", {})

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
        if not (inputs.get(field) or "").strip():
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

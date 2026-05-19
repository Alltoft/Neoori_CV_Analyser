from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, Response, stream_with_context
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from ..extensions import db
from ..models.analysis import Analysis

_STALE_THRESHOLD = timedelta(minutes=10)
from ..utils.tokens import generate_share_token
from ..services.anthropic_service import stream_analysis

analyses_bp = Blueprint("analyses", __name__)

_REQUIRED_INPUTS = [
    "cible_visee", "prenom", "tranche_age",
    "localisation", "situation_actuelle", "type_mobilite",
]


@analyses_bp.post("/")
def create_analysis():
    user_id = _optional_user_id()
    data = request.get_json(silent=True) or {}
    inputs = dict(data.get("inputs", {}))
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


@analyses_bp.get("/<analysis_id>/stream")
def run_analysis_stream(analysis_id):
    analysis = Analysis.query.get_or_404(analysis_id)

    is_stale = (
        analysis.status == "running"
        and datetime.utcnow() - analysis.created_at > _STALE_THRESHOLD
    )
    if analysis.status not in ("queued", "error", "timeout") and not is_stale:
        return jsonify({"error": f"Statut incompatible : {analysis.status}"}), 409

    return Response(
        stream_with_context(stream_analysis(analysis_id)),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


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

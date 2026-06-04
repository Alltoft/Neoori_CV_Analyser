from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db
from ..models.prompt_version import PromptVersion
from ..utils.decorators import admin_required

prompts_bp = Blueprint("prompts", __name__)


@prompts_bp.get("/")
@jwt_required()
def list_prompts():
    """All prompt versions, newest first. Text excluded to keep payload small."""
    versions = PromptVersion.query.order_by(PromptVersion.created_at.desc()).all()
    return jsonify({"prompts": [p.to_dict(include_text=False) for p in versions]}), 200


@prompts_bp.get("/active")
def get_active_prompt():
    """Public — returns the currently active prompt for a given path (default 'A')."""
    path = (request.args.get("path") or "A").upper()
    if path not in ("A", "B"):
        return jsonify({"error": "path doit être 'A' ou 'B'."}), 400
    prompt = PromptVersion.query.filter_by(is_active=True, path=path).first()
    if not prompt:
        return jsonify({"error": "Aucun prompt actif."}), 404
    return jsonify({"prompt": prompt.to_dict()}), 200


@prompts_bp.get("/<prompt_id>")
@admin_required
def get_prompt(prompt_id):
    prompt = PromptVersion.query.get_or_404(prompt_id)
    return jsonify({"prompt": prompt.to_dict()}), 200


@prompts_bp.post("/")
@admin_required
def create_prompt():
    """Publish a new prompt version. Optionally activate it immediately."""
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    version_label = (data.get("version_label") or "").strip()
    system_prompt_text = (data.get("system_prompt_text") or "").strip()
    activate = data.get("activate", False)
    path = (data.get("path") or "A").upper()
    if path not in ("A", "B"):
        return jsonify({"error": "path doit être 'A' ou 'B'."}), 400

    if not version_label or not system_prompt_text:
        return jsonify({"error": "version_label et system_prompt_text requis."}), 400

    if PromptVersion.query.filter_by(version_label=version_label).first():
        return jsonify({"error": f"Version '{version_label}' existe déjà."}), 409

    if activate:
        PromptVersion.query.filter_by(is_active=True, path=path).update({"is_active": False})

    prompt = PromptVersion(
        version_label=version_label,
        system_prompt_text=system_prompt_text,
        author_id=user_id,
        is_active=activate,
        path=path,
    )
    db.session.add(prompt)
    db.session.commit()
    return jsonify({"prompt": prompt.to_dict()}), 201


@prompts_bp.post("/<prompt_id>/activate")
@admin_required
def activate_prompt(prompt_id):
    """Set this version as active, deactivate all others."""
    prompt = PromptVersion.query.get_or_404(prompt_id)
    PromptVersion.query.filter_by(is_active=True, path=prompt.path).update({"is_active": False})
    prompt.is_active = True
    db.session.commit()
    return jsonify({"prompt": prompt.to_dict()}), 200


@prompts_bp.post("/<prompt_id>/rollback")
@admin_required
def rollback_prompt(prompt_id):
    """Alias for activate — kept as explicit intent in the UI."""
    return activate_prompt(prompt_id)

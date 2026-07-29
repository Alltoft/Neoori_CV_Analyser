from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..extensions import db
from ..models.prompt_version import PromptVersion
from ..services import section_registry as registry
from ..utils.decorators import admin_required

prompts_bp = Blueprint("prompts", __name__)

_PATHS_LABEL = ", ".join(f"'{p}'" for p in registry.PARCOURS)


def _read_path(raw):
    """Validate a parcours id from the request, accepting legacy 'A'/'B'.

    Returns (path, error_response). Rows written before the 3-parcours
    migration still carry the old codes, so the admin UI can address them.
    """
    value = (raw or registry.DEFAULT_PARCOURS).strip().upper()
    if value in ("A", "B"):
        return registry.normalize(value), None
    if not registry.is_valid(value):
        return None, (jsonify({"error": f"path doit être l'un de {_PATHS_LABEL}."}), 400)
    return value, None


@prompts_bp.get("/")
@jwt_required()
def list_prompts():
    """All prompt versions, newest first. Text excluded to keep payload small."""
    query = PromptVersion.query
    path = request.args.get("path")
    if path:
        resolved, error = _read_path(path)
        if error:
            return error
        query = query.filter_by(path=resolved)
    versions = query.order_by(PromptVersion.created_at.desc()).all()
    return jsonify({"prompts": [p.to_dict(include_text=False) for p in versions]}), 200


@prompts_bp.get("/active")
def get_active_prompt():
    """Public — the active prompt for a parcours (default '1')."""
    path, error = _read_path(request.args.get("path"))
    if error:
        return error
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
    path, error = _read_path(data.get("path"))
    if error:
        return error

    if not version_label or not system_prompt_text:
        return jsonify({"error": "version_label et system_prompt_text requis."}), 400

    # Scoped to the parcours: the same label may exist once per parcours.
    # It used to be a global check, so "v1.7" could only ever belong to one.
    if PromptVersion.query.filter_by(version_label=version_label, path=path).first():
        return jsonify({"error": f"Version '{version_label}' existe déjà pour ce parcours."}), 409

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

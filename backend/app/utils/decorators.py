from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request


def role_required(*roles):
    """Restrict endpoint to one or more roles. Usage: @role_required('admin')"""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            if claims.get("role") not in roles:
                return jsonify({"error": "Accès non autorisé."}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def admin_required(fn):
    return role_required("admin")(fn)


def candidate_or_admin(fn):
    return role_required("candidate", "admin")(fn)


def approved_counselor_required(fn):
    """A conseiller surface: the claim says counselor AND the DB still agrees.

    role_required alone reads the JWT claim, which survives a revocation for up
    to JWT_ACCESS_TOKEN_EXPIRES (1 h, config.py:23). Revocation has to bite on
    the next request, so this one pays for a row read.

    Admins pass without a profile, the exception every /api/voyage/c/<token>
    route already makes.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        # Imported here, not at module scope: app.models imports the extensions
        # this module is loaded alongside, and a top-level import would make
        # that circular.
        from ..models.counselor_profile import CounselorProfile

        verify_jwt_in_request()
        role = get_jwt().get("role")
        if role == "admin":
            return fn(*args, **kwargs)
        if role != "counselor":
            return jsonify({"error": "Accès non autorisé."}), 403

        profile = CounselorProfile.query.filter_by(user_id=get_jwt_identity()).first()
        if profile is None or profile.status != "approved":
            return jsonify({"error": "Accès non autorisé."}), 403
        return fn(*args, **kwargs)
    return wrapper

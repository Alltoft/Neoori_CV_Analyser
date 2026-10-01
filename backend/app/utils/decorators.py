from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request


def _current_role():
    """The role the users row holds now, or None if the row is gone.

    Never the token's "role" claim: that is a snapshot from when the access
    token was minted, and it lives up to JWT_ACCESS_TOKEN_EXPIRES (1 h,
    config.py:23). An approval read from the claim left a new conseiller locked
    out of their espace until they signed out and back in; a revocation or a
    demotion read from it kept the door open for the rest of the hour. One
    primary-key read per guarded request makes both bite on the next one.
    """
    # Imported here, not at module scope: app.models imports the extensions
    # this module is loaded alongside, and a top-level import would make that
    # circular.
    from ..models.user import User

    verify_jwt_in_request()
    user = User.query.get(get_jwt_identity())
    return user.role if user else None


def role_required(*roles):
    """Restrict endpoint to one or more roles. Usage: @role_required('admin')"""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if _current_role() not in roles:
                return jsonify({"error": "Accès non autorisé."}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def admin_required(fn):
    return role_required("admin")(fn)


def candidate_or_admin(fn):
    return role_required("candidate", "admin")(fn)


def approved_counselor_required(fn):
    """A conseiller surface: the users row says counselor AND the profile is
    still approved.

    The two normally move together (admin._decide), but the profile is what an
    admin revokes, so it is read too rather than trusted through the role.

    Admins pass without a profile, the exception every /api/voyage/c/<token>
    route already makes.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        from ..models.counselor_profile import CounselorProfile

        role = _current_role()
        if role == "admin":
            return fn(*args, **kwargs)
        if role != "counselor":
            return jsonify({"error": "Accès non autorisé."}), 403

        profile = CounselorProfile.query.filter_by(user_id=get_jwt_identity()).first()
        if profile is None or profile.status != "approved":
            return jsonify({"error": "Accès non autorisé."}), 403
        return fn(*args, **kwargs)
    return wrapper

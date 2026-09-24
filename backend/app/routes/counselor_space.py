"""The conseiller's own surface: /api/counselor/*.

Not to be confused with routes/counselor.py, mounted at /api/c — that one
serves an analysis share link to whoever holds the token, with no account at
all. This blueprint is the account.
"""
from datetime import datetime

from flask import Blueprint, jsonify
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
    set_access_cookies,
    set_refresh_cookies,
    verify_jwt_in_request,
)

from ..extensions import bcrypt, db
from ..models.counselor_profile import CounselorProfile
from ..models.user import User
from ..utils.request_body import json_object, raw_text_field, text_field

counselor_space_bp = Blueprint("counselor_space", __name__)

REQUIRED_FIELDS = ("structure", "fonction", "telephone")


@counselor_space_bp.post("/apply")
def apply():
    """Submit a demande — with or without an account already.

    An existing candidate applies from their espace and keeps the account they
    have; without a JWT the account is created here. Either way the person
    stays role='candidate' until an admin approves: the JWT claim is what every
    counselor guard reads, so granting the role now would open
    /api/voyage/c/<token> to someone nobody has reviewed.

    This is the app's only public endpoint that creates an account *and*
    enqueues admin work. v1 leans on the unique-email constraint and on a human
    reading the queue; a rate limit belongs here if demandes are ever spammed.
    """
    verify_jwt_in_request(optional=True)
    user_id = get_jwt_identity()

    data = json_object()
    fields = {name: text_field(data, name) for name in REQUIRED_FIELDS}
    missing = [name for name, value in fields.items() if not value]
    if missing:
        return jsonify({"error": "Structure, fonction et téléphone sont requis."}), 400
    if data.get("consent") is not True:
        return jsonify({"error": "Le consentement est requis."}), 400

    if user_id:
        user = User.query.get(user_id)
        if user is None:
            return jsonify({"error": "Utilisateur introuvable."}), 404
        # An admin must never hold a demande. Deciding one rewrites user.role
        # (routes/admin.py::_decide), so approving or refusing an admin's own
        # demande would demote them — and on the single-admin install this
        # project runs, that locks everyone out of /admin with no UI recovery.
        # admin.py:155-160 already refuses the same thing for the role editor.
        if user.role == "admin":
            return jsonify({
                "error": "Un compte administrateur ne peut pas demander un compte conseiller."
            }), 409
        created = False
    else:
        email = text_field(data, "email").lower()
        password = raw_text_field(data, "password")
        if not email or not password:
            return jsonify({"error": "Email et mot de passe requis."}), 400
        if len(password) < 8:
            return jsonify({"error": "Le mot de passe doit contenir au moins 8 caractères."}), 400
        if User.query.filter_by(email=email).first():
            return jsonify({"error": "Un compte existe déjà avec cet email."}), 409
        user = User(
            email=email,
            password_hash=bcrypt.generate_password_hash(password).decode("utf-8"),
        )
        db.session.add(user)
        db.session.flush()   # user.id, for the profile's FK
        created = True

    if CounselorProfile.query.filter_by(user_id=user.id).first():
        return jsonify({"error": "Une demande existe déjà pour ce compte."}), 409

    profile = CounselorProfile(
        user_id=user.id,
        email_pro=text_field(data, "email_pro") or None,
        message=text_field(data, "message") or None,
        **fields,
    )
    db.session.add(profile)
    db.session.commit()

    response = jsonify({"user": user.to_dict(), "profile": profile.to_dict()})
    if created:
        access_token = create_access_token(
            identity=user.id, additional_claims={"role": user.role}
        )
        set_access_cookies(response, access_token)
        set_refresh_cookies(response, create_refresh_token(identity=user.id))
    return response, 201


@counselor_space_bp.get("/me")
@jwt_required()
def me():
    """The demande and its status — the switch the /conseiller page renders from.

    Deliberately not behind approved_counselor_required: the whole point is to
    be readable while pending, rejected or revoked.
    """
    profile = CounselorProfile.query.filter_by(user_id=get_jwt_identity()).first()
    return jsonify({"profile": profile.to_dict() if profile else None}), 200

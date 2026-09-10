from flask import Blueprint, jsonify
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
    get_jwt,
    set_access_cookies,
    set_refresh_cookies,
    unset_jwt_cookies,
)
from ..extensions import db, bcrypt
from ..models.user import User
from ..utils.request_body import json_object, text_field, raw_text_field

auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/register")
def register():
    data = json_object()
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
    db.session.commit()

    response = jsonify({"user": user.to_dict()})
    _set_tokens(response, user)
    return response, 201


@auth_bp.post("/login")
def login():
    data = json_object()
    email = text_field(data, "email").lower()
    password = raw_text_field(data, "password")

    user = User.query.filter_by(email=email).first()
    if not user or not bcrypt.check_password_hash(user.password_hash, password):
        return jsonify({"error": "Identifiants incorrects."}), 401

    response = jsonify({"user": user.to_dict()})
    _set_tokens(response, user)
    return response, 200


@auth_bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "Utilisateur introuvable."}), 404

    access_token = create_access_token(
        identity=user.id,
        additional_claims={"role": user.role},
    )
    response = jsonify({"user": user.to_dict()})
    set_access_cookies(response, access_token)
    return response, 200


@auth_bp.post("/logout")
def logout():
    response = jsonify({"message": "Déconnecté."})
    unset_jwt_cookies(response)
    return response, 200


@auth_bp.get("/me")
@jwt_required()
def me():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "Utilisateur introuvable."}), 404
    return jsonify({"user": user.to_dict()}), 200


# ── helpers ──────────────────────────────────────────────────────────────────

def _set_tokens(response, user: User):
    access_token = create_access_token(
        identity=user.id,
        additional_claims={"role": user.role},
    )
    refresh_token = create_refresh_token(identity=user.id)
    set_access_cookies(response, access_token)
    set_refresh_cookies(response, refresh_token)

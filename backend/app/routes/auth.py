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
from datetime import datetime

from ..extensions import db, bcrypt
from ..models.profile import ACCEPTED_AGE_BRACKETS, CONSENT_VERSION, Profile
from ..models.user import User
from ..services import auth_mail
from ..utils import auth_links
from ..utils.request_body import json_object, text_field, raw_text_field

auth_bp = Blueprint("auth", __name__)

# The two fields session_lock has demanded before S1 since the voyage shipped.
# Collected here because this is the only moment the person is already filling
# a form: asking for them mid-journey is the bounce to /profil that the PM's
# placement exists to remove.
SEED_FIELDS = ("prenom", "tranche_age")


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

    # Validated before the account exists, so a refused seed never leaves a
    # user behind who has to pick another email to try again.
    seed = {field: text_field(data, field) for field in SEED_FIELDS}
    seed = {field: value for field, value in seed.items() if value}
    if seed:
        if data.get("consent") is not True:
            return jsonify({"error": "Le consentement est requis."}), 400
        bracket = seed.get("tranche_age")
        if bracket and bracket not in ACCEPTED_AGE_BRACKETS:
            return jsonify({"error": "Valeur invalide pour tranche_age."}), 400

    user = User(
        email=email,
        password_hash=bcrypt.generate_password_hash(password).decode("utf-8"),
    )
    db.session.add(user)
    db.session.flush()  # user.id, for the profile's FK

    if seed:
        db.session.add(Profile(
            user_id=user.id,
            consent_at=datetime.utcnow(),
            consent_version=CONSENT_VERSION,
            **seed,
        ))

    db.session.commit()

    # No session: the account opens once its address is proven (spec decision
    # 2). `next` rides in the link, so the email round-trip lands them back
    # where they were heading.
    mail_sent = auth_mail.verification_if_due(user, text_field(data, "next") or None)
    return jsonify({"user": user.to_dict(), "mail_sent": mail_sent}), 201


@auth_bp.post("/login")
def login():
    data = json_object()
    email = text_field(data, "email").lower()
    password = raw_text_field(data, "password")

    user = User.query.filter_by(email=email).first()
    if not user or not bcrypt.check_password_hash(user.password_hash, password):
        return jsonify({"error": "Identifiants incorrects."}), 401

    # 403, not 401: api.ts sends every 401 back to /connexion, which would
    # swallow this. Reached only with the right password, so it tells the
    # account's state to its owner and nobody else (spec decision 9).
    if user.email_verified_at is None:
        return jsonify({
            "error": "Confirmez votre adresse email pour activer votre compte.",
            "code": "email_unverified",
        }), 403

    response = jsonify({"user": user.to_dict()})
    _issue_session(response, user)
    return response, 200


@auth_bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "Utilisateur introuvable."}), 404

    # A refresh token outlives a password change by up to 30 days. pwv pins it
    # to the password it was minted under, so a reset ends every other session
    # (spec decision 6). Tokens minted before pwv existed carry none and end
    # too, once.
    if (
        user.email_verified_at is None
        or get_jwt().get("pwv") != auth_links.password_fingerprint(user.password_hash)
    ):
        response = jsonify({"error": "Session expirée."})
        unset_jwt_cookies(response)
        return response, 401

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

def _issue_session(response, user: User):
    """The only place a session is minted. It refuses an unverified account, so
    a route added later cannot hand one out by forgetting a check (spec
    decision 2)."""
    if user.email_verified_at is None:
        raise ValueError("refusing to open a session for an unverified account")
    access_token = create_access_token(
        identity=user.id,
        additional_claims={"role": user.role},
    )
    refresh_token = create_refresh_token(
        identity=user.id,
        additional_claims={"pwv": auth_links.password_fingerprint(user.password_hash)},
    )
    set_access_cookies(response, access_token)
    set_refresh_cookies(response, refresh_token)

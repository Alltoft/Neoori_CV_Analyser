from flask import Blueprint, current_app, jsonify
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

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from ..extensions import db, bcrypt
from ..models.auth_identity import AuthIdentity
from ..models.counselor_profile import CounselorProfile
from ..models.profile import (
    ACCEPTED_AGE_BRACKETS, AGE_BRACKETS, CONSENT_VERSION, PRENOM_MAX_LENGTH, Profile,
)
from ..models.user import User
from ..services import auth_mail, demande_mail, email_service, held, sign_in
from ..utils import auth_links
from ..utils.request_body import json_object, text_field, raw_text_field

auth_bp = Blueprint("auth", __name__)

# The two fields session_lock has demanded before S1 since the voyage shipped.
# Collected here because this is the only moment the person is already filling
# a form: asking for them mid-journey is the bounce to /profil that the PM's
# placement exists to remove.
SEED_FIELDS = ("prenom", "tranche_age")

# bcrypt reads at most 72 bytes, and bcrypt 5 raises past that instead of
# truncating; a lone surrogate cannot be encoded at all. Both were a 500, and
# at login a 500 only when the account existed. Not solved with
# BCRYPT_HANDLE_LONG_PASSWORDS: it pre-hashes, which would stop every stored
# hash from matching.
PASSWORD_MAX_BYTES = 72


@auth_bp.post("/register")
def register():
    data = json_object()
    email = text_field(data, "email").lower()
    password = raw_text_field(data, "password")

    if not email or not password:
        return jsonify({"error": "Email et mot de passe requis."}), 400
    problem = password_problem(password)
    if problem:
        return jsonify({"error": problem}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Un compte existe déjà avec cet email."}), 409

    # Validated before the account exists, so a refused seed never leaves a
    # user behind who has to pick another email to try again.
    seed = {field: text_field(data, field) for field in SEED_FIELDS}
    seed = {field: value for field, value in seed.items() if value}
    if seed:
        problem = _seed_problem(seed, data.get("consent"))
        if problem:
            return jsonify({"error": problem}), 400

    user = User(
        email=email,
        password_hash=bcrypt.generate_password_hash(password).decode("utf-8"),
    )
    db.session.add(user)
    db.session.flush()  # user.id, for the profile's FK

    if seed:
        _add_seeded_profile(user, seed)

    db.session.commit()

    # A draft this browser holds waits for this account (four-doors spec,
    # decision 34): marked now, attached only once the signup password proves
    # the address at verify-email (decision 36). Never for an address that
    # already had an account — that answered 409 above.
    if held.mark_for(user.id):
        db.session.commit()

    # No session: the account opens once its address is proven (spec decision
    # 2). `next` rides in the link, so the email round-trip lands them back
    # where they were heading.
    mail_sent = auth_mail.verification_if_due(user, text_field(data, "next") or None)
    return jsonify({"user": user.to_dict(), "mail_sent": mail_sent}), 201


@auth_bp.get("/signup")
def signup_details():
    """What « Finaliser votre inscription » shows: the address the ticket
    proves, and the prénom the provider gave, to prefill."""
    ticket, code = sign_in.live_signup_ticket()
    if code:
        return _link_error(code)
    return jsonify({
        "email": ticket["email"],
        "prenom": ticket.get("prenom_hint") or "",
        "method": ticket["method"],
    }), 200


@auth_bp.post("/signup")
def signup():
    """The account a signup ticket was waiting for, created with its consent
    in one commit (social sign-in spec, decisions 1 and 19). Nothing exists
    before this: no users row, no session."""
    ticket, code = sign_in.live_signup_ticket()
    if code:
        return _link_error(code)

    data = json_object()
    seed = {field: text_field(data, field) for field in SEED_FIELDS}
    if not seed["prenom"]:
        return jsonify({"error": "Prénom requis."}), 400
    if not seed["tranche_age"]:
        return jsonify({"error": "Tranche d'âge requise."}), 400
    # The seven brackets the form offers: the legacy one is never asked again.
    problem = _seed_problem(seed, data.get("consent"), AGE_BRACKETS)
    if problem:
        return jsonify({"error": problem}), 400

    provider = None if ticket["method"] == "email" else ticket["method"]
    sub = ticket.get("sub")
    email = ticket["email"]
    # Another tab, or a double click, may have finished first: what it made
    # is entered, and this form overwrites nothing (decision 19).
    user = sign_in.existing_account(provider, sub, email)
    if user is None and sign_in.address_in_use(email):
        # Held already: by a racing submit that has just committed (look
        # again and enter it), or by an account whose address only collates
        # equal to this one (refuse: it is someone else's). Under MySQL's
        # default REPEATABLE READ the second look reads the same snapshot as
        # the first, so a racing twin is in practice entered by the
        # IntegrityError fallback below; the re-look helps only under READ
        # COMMITTED.
        user = sign_in.existing_account(provider, sub, email)
        if user is None:
            return jsonify({"error": ADDRESS_UNAVAILABLE, "code": "address_unavailable"}), 409
    if user is None:
        user = User(
            email=email,
            password_hash=sign_in.unusable_password_hash(),
            email_verified_at=datetime.utcnow(),   # the ticket is the proof
        )
        db.session.add(user)
        try:
            db.session.flush()   # user.id, for the identity and the profile
            if provider:
                db.session.add(AuthIdentity(user_id=user.id, provider=provider, subject=sub))
            _add_seeded_profile(user, seed)
            db.session.commit()
        except IntegrityError:
            # A concurrent submit committed the same address first — or, on
            # MySQL, a lookalike account appeared since the look above.
            current_app.logger.warning("POST /signup fell back after an IntegrityError.", exc_info=True)
            db.session.rollback()
            user = sign_in.existing_account(provider, sub, email)
            if user is None:
                return jsonify({"error": ADDRESS_UNAVAILABLE, "code": "address_unavailable"}), 409

    response = jsonify({"user": user.to_dict(), "next": _landing(user, ticket)})
    sign_in.clear_signup_ticket(response)
    _issue_session(response, user)
    return response, 200


@auth_bp.post("/login")
def login():
    data = json_object()
    email = text_field(data, "email").lower()
    password = raw_text_field(data, "password")

    user = User.query.filter_by(email=email).first()
    # password_matches never raises: a password bcrypt cannot take is a wrong
    # password, answered exactly as an unknown address is (spec decision 9).
    if not user or not password_matches(user, password):
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
    # A draft saved after the session lapsed is held by this browser's cookie,
    # not by the account (decision 38: expired means signed out). Left behind,
    # the next person on a shared computer could read it back at /held or claim
    # it into their own account, so it goes with the session. A held no-login
    # report is not touched: its own link still reaches it. No session is
    # needed, so a lapsed one can log out too.
    try:
        if held.drop_held_draft():
            db.session.commit()
    except SQLAlchemyError:
        # Best effort: ending the session must not depend on the database,
        # which logout never touched before. The cookie is cleared below
        # either way, so the browser forgets the key and the row expires.
        db.session.rollback()
        current_app.logger.warning("Logout could not delete the held draft.", exc_info=True)
    response = jsonify({"message": "Déconnecté."})
    unset_jwt_cookies(response)
    held.clear_cookie(response)
    return response, 200


@auth_bp.get("/me")
@jwt_required()
def me():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "Utilisateur introuvable."}), 404
    return jsonify({"user": user.to_dict()}), 200


LINK_ERRORS = {
    "link_expired": "Ce lien a expiré. Demandez-en un nouveau.",
    "link_invalid": "Ce lien n'est pas valide. Demandez-en un nouveau.",
}
# One sentence whatever the account's state: these two must not tell a
# stranger whether an address has an account (spec decision 11).
RESEND_MESSAGE = "Si cette adresse attend une confirmation, un nouveau lien vient d'être envoyé."
FORGOT_MESSAGE = "Si un compte existe pour cette adresse, un email vient d'être envoyé."
# A sign-in proved an address the database already files under another,
# only collation-equal account (« marie@gmaïl.com » for « marie@gmail.com »).
# Entering it would hand one person's account to another; creating a new one
# would collide with the unique index. Wording provisional (PM may reword).
ADDRESS_UNAVAILABLE = (
    "Cette adresse ne peut pas être utilisée pour se connecter. "
    "Répondez à l'email reçu pour nous écrire."
)


@auth_bp.post("/verify-email/check")
def verify_email_check():
    """Is this link alive, and for which address? Lets the page say « expiré »
    before anyone types a password, and fill the email for password managers."""
    user, _payload, code = _user_from_verify_token(text_field(json_object(), "token"))
    if code:
        return _link_error(code)
    return jsonify({"email": user.email}), 200


@auth_bp.post("/verify-email")
def verify_email():
    """Link + password → verified and signed in (spec decision 8).

    The password is what closes pre-account hijacking: someone who signed up
    with your address and their password cannot have you verify an account
    they can also log into. Without it the victim uses « mot de passe
    oublié », which sets their own password and ends the other sessions.
    A second use is simply a login.
    """
    data = json_object()
    user, payload, code = _user_from_verify_token(text_field(data, "token"))
    if code:
        return _link_error(code)

    password = raw_text_field(data, "password")
    if not password or not password_matches(user, password):
        return jsonify({"error": "Mot de passe incorrect.", "code": "wrong_password"}), 401

    if user.email_verified_at is None:
        user.email_verified_at = datetime.utcnow()
        # The link AND the signup password: the registrant. What signup marked
        # for this account is theirs.
        held.attach_pending(user.id)
        db.session.commit()
        # This address's first proof: a demande waiting on it joins the admin
        # queue now. A second use of the link is a login and skips this.
        demande_mail.notify_if_visible(user)

    response = jsonify({"user": user.to_dict(), "next": _landing(user, payload)})
    _issue_session(response, user)
    return response, 200


@auth_bp.post("/resend-verification")
def resend_verification():
    data = json_object()
    user = _user_by_email(data.get("email"))
    if user is not None and user.email_verified_at is None:
        auth_mail.verification_if_due(user, text_field(data, "next") or None)
    return jsonify({"message": RESEND_MESSAGE}), 200


@auth_bp.post("/forgot-password")
def forgot_password():
    user = _user_by_email(json_object().get("email"))
    if user is not None:
        auth_mail.reset_if_due(user)
    return jsonify({"message": FORGOT_MESSAGE}), 200


@auth_bp.post("/reset-password")
def reset_password():
    data = json_object()
    result = auth_links.load_reset_token(text_field(data, "token"))
    if result.error:
        return _link_error(result.error)
    user = _user_by_id(result.payload.get("uid"))
    # pwv dies with the password it was minted under: a used link is dead.
    if user is None or result.payload.get("pwv") != auth_links.password_fingerprint(user.password_hash):
        return _link_error("link_invalid")

    # Checked before anything is written, so a refused password leaves the
    # link usable for the next attempt.
    password = raw_text_field(data, "password")
    problem = password_problem(password)
    if problem:
        return jsonify({"error": problem}), 400

    user.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")
    # Opening the link proved the inbox, exactly as the verification link
    # does (spec decision 12).
    newly_verified = user.email_verified_at is None
    if newly_verified:
        user.email_verified_at = datetime.utcnow()
        # Proven without the signup password: whoever registered this address
        # may have been someone else (four-doors spec, decision 36).
        held.unmark(user.id)
    db.session.commit()

    # After the commit, like every mail. It reaches the address's owner even
    # when someone else held the link; not paced by auth_mail_sent_at, since
    # the link that made this reset possible already was.
    email_service.send_password_changed(user)
    if newly_verified:
        # The same first proof verify_email() reacts to, by the other door.
        demande_mail.notify_if_visible(user)

    response = jsonify({"user": user.to_dict()})
    _issue_session(response, user)
    return response, 200


# ── helpers ──────────────────────────────────────────────────────────────────

def _issue_session(response, user: User):
    """The only place a session (the refresh + access pair) is opened. It
    refuses an unverified account, so a route added later cannot hand one out
    by forgetting a check (spec decision 2). /refresh re-mints the access
    cookie alone, for a session opened here, after its own verified + pwv
    checks."""
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


def password_problem(password: str) -> str | None:
    """Why a new password cannot be stored, as the French sentence to show,
    or None. For every route that sets one: register, reset-password and the
    conseiller demande (counselor_space.apply)."""
    if len(password) < 8:
        return "Le mot de passe doit contenir au moins 8 caractères."
    size = _password_bytes(password)
    if size is None:
        return "Le mot de passe contient un caractère non pris en charge."
    if size > PASSWORD_MAX_BYTES:
        return "Le mot de passe est trop long : 72 caractères maximum, un peu moins avec des accents."
    return None


def password_matches(user: User, password: str) -> bool:
    """bcrypt's check, minus its exceptions. A password bcrypt cannot take is
    simply not this account's password, so login and verify-email answer it
    as they answer any wrong one."""
    size = _password_bytes(password)
    if size is None or size > PASSWORD_MAX_BYTES:
        return False
    return bcrypt.check_password_hash(user.password_hash, password)


def _password_bytes(password: str) -> int | None:
    """UTF-8 length, or None for a string that cannot be encoded (a lone
    surrogate, which JSON can carry)."""
    try:
        return len(password.encode("utf-8"))
    except UnicodeEncodeError:
        return None


def _seed_problem(seed: dict, consent, brackets=ACCEPTED_AGE_BRACKETS) -> str | None:
    """Why a signup's profile seed cannot be stored, as the sentence to show,
    or None. register and signup share it: they are the two signup doors
    that write a first consent (social sign-in spec, decision 20). PUT
    /api/profile writes one too, without this length check (a known,
    separate gap). The length check is the one SQLite never makes and MySQL
    answers with an error."""
    if consent is not True:
        return "Le consentement est requis."
    bracket = seed.get("tranche_age")
    if bracket and bracket not in brackets:
        return "Valeur invalide pour tranche_age."
    prenom = seed.get("prenom", "")
    if len(prenom) > PRENOM_MAX_LENGTH:
        return f"Le prénom est trop long : {PRENOM_MAX_LENGTH} caractères maximum."
    try:
        prenom.encode("utf-8")
    except UnicodeEncodeError:
        return "Le prénom contient un caractère non pris en charge."
    return None


def _add_seeded_profile(user: User, seed: dict) -> None:
    """The Profil de base row a signup opens, with the consent just given."""
    db.session.add(Profile(
        user_id=user.id,
        consent_at=datetime.utcnow(),
        consent_version=CONSENT_VERSION,
        **seed,
    ))


def _link_error(code: str):
    return jsonify({"error": LINK_ERRORS[code], "code": code}), 400


def _user_by_email(raw) -> User | None:
    """The account for an address typed into a form. One normalisation, the
    one register stores under (strip, then lower): resend and forgot must find
    the same account for « Marie@Test.FR » and « marie@test.fr »."""
    email = raw.strip().lower() if isinstance(raw, str) else ""
    return User.query.filter_by(email=email).first() if email else None


def _user_by_id(uid) -> User | None:
    """The account a signed link names. The id comes out of a payload, so a
    non-string is refused here rather than handed to the database."""
    return db.session.get(User, uid) if isinstance(uid, str) else None


def _user_from_verify_token(token: str):
    """(user, payload, None) for a live verification link, else (None, None, code)."""
    result = auth_links.load_verify_token(token)
    if result.error:
        return None, None, result.error
    user = _user_by_id(result.payload.get("uid"))
    # The address is in the signed payload: a link mailed to an address the
    # account no longer holds proves nothing about the current one.
    if user is None or user.email != result.payload.get("email"):
        return None, None, "link_invalid"
    return user, result.payload, None


def _landing(user: User, payload: dict) -> str | None:
    """Where the verified person goes. A conseiller who asked for a fresh link
    from /connexion carries no next; their screen is the demande, not the
    candidate espace (spec decision 23).

    `next` is returned exactly as it was signed: safe_next admits strings such
    as « /%2F%2Fevil.com » that are harmless only when used verbatim."""
    if payload.get("next"):
        return payload["next"]
    if CounselorProfile.query.filter_by(user_id=user.id).first():
        return "/conseiller"
    return None

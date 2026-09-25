"""The conseiller's own surface: /api/counselor/*.

Not to be confused with routes/counselor.py, mounted at /api/c — that one
serves an analysis share link to whoever holds the token, with no account at
all. This blueprint is the account.
"""
from datetime import datetime, timedelta

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
from flask_jwt_extended.exceptions import JWTExtendedException
from jwt import PyJWTError

from ..extensions import bcrypt, db
from ..models.code_redemption import CodeRedemption
from ..models.counselor_code import CounselorCode
from ..models.counselor_profile import CounselorProfile
from ..models.profile import Profile
from ..models.user import User
from ..models.voyage import Voyage
from ..services import code_service
from ..utils.decorators import approved_counselor_required
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
    # optional=True swallows only a MISSING token. A present-but-expired or
    # malformed one still raises, and the app-wide JWT error handlers
    # (app/__init__.py:196-202) would turn it into 401 « Session expirée. »
    # before this function runs — locking a visitor whose hour-old session
    # lapsed out of a form they are entitled to use while logged out.
    # A token we cannot trust is the same as no token here.
    try:
        verify_jwt_in_request(optional=True)
        user_id = get_jwt_identity()
    except (JWTExtendedException, PyJWTError):
        user_id = None

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


# A conseiller-minted code is for one person unless they say otherwise, and it
# stops being valid after this long. An unredeemed single-use code would
# otherwise stay live for ever: mint fifty, use twelve, and thirty-eight are
# still in circulation a year later.
DEFAULT_MAX_USES = 1
DEFAULT_EXPIRY_DAYS = 90

# A code nobody could outlive is not a feature, and an int wide enough to
# overflow timedelta() or the INTEGER column is a 500 waiting to happen.
# Both are clamped rather than refused, for the same reason max_uses already
# is: the caller gets the nearest sane value they would have typed.
MAX_USES_CEILING = 1000       # far past any atelier
MAX_EXPIRY_DAYS = 3650        # ten years, far past any accompagnement


def _profile_or_none():
    return CounselorProfile.query.filter_by(user_id=get_jwt_identity()).first()


def _code_row(code: CounselorCode, uses: int) -> dict:
    """The code, its real use count, and one French status for the table."""
    if code.revoked_at is not None or not code.is_active:
        statut = "revoque"
    elif code.max_uses is not None and uses >= code.max_uses:
        statut = "utilise"
    elif code.expires_at is not None and code.expires_at <= datetime.utcnow():
        statut = "expire"
    else:
        statut = "actif"
    return {**code.to_dict(), "uses": uses, "statut": statut}


def _use_counts(code_ids: list[str]) -> dict[str, int]:
    """One grouped query instead of a count per row."""
    if not code_ids:
        return {}
    rows = (
        db.session.query(CodeRedemption.code_id, db.func.count(CodeRedemption.id))
        .filter(CodeRedemption.code_id.in_(code_ids))
        .group_by(CodeRedemption.code_id)
        .all()
    )
    return {code_id: count for code_id, count in rows}


@counselor_space_bp.get("/codes")
@approved_counselor_required
def list_codes():
    codes = (
        CounselorCode.query
        .filter_by(owner_id=get_jwt_identity())
        .order_by(CounselorCode.created_at.desc())
        .all()
    )
    counts = _use_counts([c.id for c in codes])
    return jsonify({"codes": [_code_row(c, counts.get(c.id, 0)) for c in codes]}), 200


@counselor_space_bp.post("/codes")
@approved_counselor_required
def create_code():
    """Mint a code, inside the admin's two dials.

    max_uses is clamped rather than refused: a conseiller asking for more
    places than their ceiling gets the ceiling, which is what they would have
    typed had they known it. max_codes is refused, because there is no
    smaller version of "one more code".
    """
    # A row lock on the profile, mirroring code_service.resolve(). The same
    # caveat applies: MySQL's REPEATABLE READ snapshot is fixed before the lock
    # is taken, so the count below can be stale and two overlapped mints can
    # both pass. This narrows the window rather than closing it — max_codes is
    # enforced against sequential minting, not against a deliberate race.
    # SQLite (tests) omits the clause silently; the check itself still runs.
    profile = (
        CounselorProfile.query
        .filter_by(user_id=get_jwt_identity())
        .with_for_update()
        .first()
    )
    if profile is None:
        return jsonify({"error": "Accès non autorisé."}), 403

    data = json_object()
    label = text_field(data, "label")
    if not label:
        return jsonify({"error": "Un libellé est requis."}), 400

    if profile.max_codes is not None:
        # Codes ever created, not codes still active: counting active ones lets
        # a revoked code be re-minted for ever (spec decision 5).
        created = CounselorCode.query.filter_by(owner_id=profile.user_id).count()
        if created >= profile.max_codes:
            return jsonify({
                "error": "Vous avez atteint votre nombre de codes autorisé."
            }), 409

    requested = data.get("max_uses")
    max_uses = requested if isinstance(requested, int) and not isinstance(requested, bool) else DEFAULT_MAX_USES
    max_uses = max(1, max_uses)
    if profile.max_uses_per_code is not None:
        max_uses = min(max_uses, profile.max_uses_per_code)
    max_uses = min(max_uses, MAX_USES_CEILING)

    days = data.get("expires_in_days")
    days = days if isinstance(days, int) and not isinstance(days, bool) and days > 0 else DEFAULT_EXPIRY_DAYS
    days = min(days, MAX_EXPIRY_DAYS)

    code = CounselorCode(
        label=label,
        owner_id=profile.user_id,
        created_by_id=profile.user_id,
        max_uses=max_uses,
        expires_at=datetime.utcnow() + timedelta(days=days),
    )
    db.session.add(code)
    db.session.commit()
    return jsonify({"code": _code_row(code, 0)}), 201


@counselor_space_bp.delete("/codes/<code_id>")
@approved_counselor_required
def revoke_code(code_id):
    """Revoke an unredeemed code. A redeemed one stays: the bénéficiaire has
    already been unlocked by it, and the row is their trace on the dashboard."""
    code = CounselorCode.query.get_or_404(code_id)
    if code.owner_id != get_jwt_identity():
        return jsonify({"error": "Accès non autorisé."}), 403
    if code_service.redemption_count(code.id) > 0:
        return jsonify({"error": "Ce code a déjà été utilisé."}), 409

    code.is_active = False
    code.revoked_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"code": _code_row(code, 0)}), 200


def _my_code_ids(user_id: str) -> list[str]:
    return [row.id for row in CounselorCode.query.filter_by(owner_id=user_id).all()]


@counselor_space_bp.get("/stats")
@approved_counselor_required
def stats():
    """The four tiles.

    « Bénéficiaires » counts redemptions and « Accompagnements » counts
    portraits this conseiller validated. Kept apart on purpose: handing out a
    code is not the same as doing the work.
    """
    profile = _profile_or_none()
    if profile is None:
        return jsonify({"error": "Accès non autorisé."}), 403
    user_id = profile.user_id

    codes = CounselorCode.query.filter_by(owner_id=user_id).all()
    counts = _use_counts([c.id for c in codes])
    now = datetime.utcnow()

    in_circulation = sum(
        1
        for c in codes
        if c.is_active
        and c.revoked_at is None
        and (c.expires_at is None or c.expires_at > now)
        and (c.max_uses is None or counts.get(c.id, 0) < c.max_uses)
    )

    return jsonify({
        "beneficiaires": sum(counts.values()),
        "accompagnements": Voyage.query.filter_by(validated_by_id=user_id).count(),
        "codes_crees": len(codes),
        "max_codes": profile.max_codes,
        "codes_restants": (
            None if profile.max_codes is None else max(0, profile.max_codes - len(codes))
        ),
        "codes_en_circulation": in_circulation,
        "max_uses_per_code": profile.max_uses_per_code,
    }), 200


@counselor_space_bp.get("/beneficiaires")
@approved_counselor_required
def beneficiaires():
    """Who used my codes, and when. Nothing they wrote.

    Reaching a voyage or a report still requires the person to hand over their
    own token — spec decision 9. No id and no token leaves this route.
    """
    code_ids = _my_code_ids(get_jwt_identity())
    if not code_ids:
        return jsonify({"beneficiaires": []}), 200

    rows = (
        db.session.query(CodeRedemption, User, Profile)
        .outerjoin(User, User.id == CodeRedemption.user_id)
        .outerjoin(Profile, Profile.user_id == User.id)
        .filter(CodeRedemption.code_id.in_(code_ids))
        .order_by(CodeRedemption.redeemed_at.desc())
        .all()
    )
    return jsonify({"beneficiaires": [
        {
            "prenom": profile.prenom if profile else None,
            "email": user.email if user else None,
            "target_type": redemption.target_type,
            "redeemed_at": redemption.redeemed_at.isoformat(),
        }
        for redemption, user, profile in rows
    ]}), 200

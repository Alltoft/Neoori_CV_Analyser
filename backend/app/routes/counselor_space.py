"""The conseiller's own surface: /api/counselor/*.

routes/counselor.py, mounted at /api/c, served an analysis share link until
the four-doors spec retired it. This blueprint is the account: its codes, its
beneficiaires and the advisor-door reports sent to it.
"""
import re
from datetime import datetime, timedelta

from flask import Blueprint, current_app, jsonify
from flask_jwt_extended import (
    get_jwt_identity,
    jwt_required,
    verify_jwt_in_request,
)
from flask_jwt_extended.exceptions import JWTExtendedException
from jwt import PyJWTError

from .. import reap_if_orphaned
from ..extensions import bcrypt, db
from ..models.analysis import Analysis
from ..models.code_redemption import CodeRedemption
from ..models.counselor_code import CounselorCode
from ..models.counselor_note import CounselorNote
from ..models.counselor_profile import (
    DOMAINES,
    TYPE_SIRET_OPTIONAL,
    TYPES_STRUCTURE,
    CounselorProfile,
)
from ..models.price_feedback import PriceFeedback
from ..models.profile import Profile
from ..models.user import User
from ..models.voyage import Voyage
from ..services import auth_mail, code_service, demande_mail, doors
from ..services.anthropic_service import start_analysis
from ..utils.decorators import approved_counselor_required
from ..utils.request_body import json_object, raw_text_field, text_field
from .auth import password_problem

counselor_space_bp = Blueprint("counselor_space", __name__)

REQUIRED_FIELDS = (
    "structure",
    "type_structure",
    "adresse_rue",
    "adresse_code_postal",
    "adresse_ville",
    "nom_complet",
    "fonction",
    "telephone",
)

_SIRET_DIGITS = re.compile(r"\D")


def _siret_or_error(raw: str, type_structure: str) -> tuple[str | None, str | None]:
    """A 14-digit SIRET, or the French refusal.

    Format only, as the PM asked — digits and length. No Luhn check: a handful
    of genuine SIRETs (La Poste's, famously) fail the checksum, and refusing a
    real structure its account is worse than accepting a typo an admin will see
    on the demande anyway.

    Optional for an indépendant, who may not have registered one yet — but if
    they type one, it is checked like everyone else's.
    """
    digits = _SIRET_DIGITS.sub("", raw)
    if not digits:
        if type_structure == TYPE_SIRET_OPTIONAL:
            return None, None
        return None, "Le SIRET est requis."
    if len(digits) != 14:
        return None, "Le SIRET doit contenir 14 chiffres."
    return digits, None


def _validate_demande(data: dict) -> tuple[dict | None, str | None]:
    """The demande's own fields, or the first French refusal.

    Account fields (email, password) are checked by the caller, because they
    only apply when there is no session yet.
    """
    fields = {name: text_field(data, name) for name in REQUIRED_FIELDS}
    if any(not value for value in fields.values()):
        return None, "Tous les champs marqués sont requis."

    if fields["type_structure"] not in TYPES_STRUCTURE:
        return None, "Type de structure invalide."

    autre = text_field(data, "type_structure_autre")
    if fields["type_structure"] == "autre" and not autre:
        return None, "Précisez le type de structure."

    siret, error = _siret_or_error(text_field(data, "siret"), fields["type_structure"])
    if error:
        return None, error

    raw_domaines = data.get("domaines")
    domaines = [d for d in raw_domaines if d in DOMAINES] if isinstance(raw_domaines, list) else []
    if not domaines:
        return None, "Choisissez au moins un domaine d'activité."

    return {
        **fields,
        "type_structure_autre": autre or None,
        "siret": siret,
        "domaines": domaines,
    }, None


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
    fields, error = _validate_demande(data)
    if error:
        return jsonify({"error": error}), 400
    # Two separate ticks since the PM's 2026-09-30 form: the terms, and the
    # consent to process the person's own professional data. Keyed on presence
    # of True so a missing box is a refusal rather than a silent pass.
    if data.get("consent") is not True:
        return jsonify({"error": "Vous devez accepter les CGV."}), 400
    if data.get("consent_donnees") is not True:
        return jsonify({"error": "Le consentement au traitement des données est requis."}), 400

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
        # register's rule, so a password bcrypt cannot take is a 400 here too
        # rather than a 500 at the hash below.
        problem = password_problem(password)
        if problem:
            return jsonify({"error": problem}), 400
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

    # email_pro and message are no longer asked for: the PM merged the
    # professional email into the account email, and removed « Précisions ».
    # Both columns survive for the rows that answered them.
    profile = CounselorProfile(user_id=user.id, **fields)
    db.session.add(profile)
    db.session.commit()

    body = {"user": user.to_dict(), "profile": profile.to_dict()}
    if created:
        # A new account opens only once its address is proven (email
        # verification spec, decision 2): no session here, a link instead,
        # landing on the « demande en attente » screen. The demande waits for
        # the same proof before the admin queue shows it (decision 16).
        body["mail_sent"] = auth_mail.verification_if_due(user, "/conseiller")
    else:
        # Signed in means a proven address (no session before one), so this
        # demande is in the admin queue from the commit above.
        demande_mail.notify_if_visible(user)
    return jsonify(body), 201


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


_NO_USES = {"analysis": 0, "voyage": 0}


def _code_row(code: CounselorCode, uses: dict[str, int]) -> dict:
    """The code, its real use counts per kind, and one French status.

    « utilisé » once BOTH kinds are spent: a single-use code opens one
    analysis and one voyage (four-doors spec, ruling 10)."""
    if code.revoked_at is not None or not code.is_active:
        statut = "revoque"
    elif code.max_uses is not None and min(uses.values()) >= code.max_uses:
        statut = "utilise"
    elif code.expires_at is not None and code.expires_at <= datetime.utcnow():
        statut = "expire"
    else:
        statut = "actif"
    return {**code.to_dict(), "uses": sum(uses.values()), "uses_by_kind": uses, "statut": statut}


@counselor_space_bp.get("/codes")
@approved_counselor_required
def list_codes():
    codes = (
        CounselorCode.query
        .filter_by(owner_id=get_jwt_identity())
        .order_by(CounselorCode.created_at.desc())
        .all()
    )
    counts = code_service.use_counts_by_kind([c.id for c in codes])
    return jsonify({"codes": [_code_row(c, counts.get(c.id, dict(_NO_USES))) for c in codes]}), 200


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
    # caveat applies, as code_service.redeem()'s docstring describes it:
    # MySQL's REPEATABLE READ snapshot is fixed before the lock is taken, so
    # the count below can be stale and two overlapped mints can both pass.
    # This narrows the window rather than closing it — max_codes is enforced
    # against sequential minting, not against a deliberate race.
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
    return jsonify({"code": _code_row(code, dict(_NO_USES))}), 201


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
    return jsonify({"code": _code_row(code, dict(_NO_USES))}), 200


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
    counts = code_service.use_counts_by_kind([c.id for c in codes])
    now = datetime.utcnow()

    in_circulation = sum(
        1
        for c in codes
        if c.is_active
        and c.revoked_at is None
        and (c.expires_at is None or c.expires_at > now)
        and (c.max_uses is None or min(counts.get(c.id, _NO_USES).values()) < c.max_uses)
    )

    return jsonify({
        "beneficiaires": sum(sum(v.values()) for v in counts.values()),
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
    """Who used my codes, and when — and, for an analysis sent through the
    advisor door, the report itself (four-doors spec, ruling 2, which reverses
    conseiller spec decision 9). A voyage is still reached only through the
    token the person hands over."""
    me = get_jwt_identity()
    code_ids = _my_code_ids(me)
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
    analysis_ids = [r.target_id for r, _u, _p in rows if r.target_type == "analysis"]
    mine = {
        a.id: a for a in Analysis.query.filter(
            Analysis.id.in_(analysis_ids), Analysis.counselor_id == me, Analysis.door == doors.ADVISOR,
        ).all()
    } if analysis_ids else {}

    people = []
    for redemption, user, profile in rows:
        report = mine.get(redemption.target_id) if redemption.target_type == "analysis" else None
        inputs = (report.inputs or {}) if report is not None else {}
        people.append({
            "prenom": inputs.get("prenom") or (profile.prenom if profile else None),
            "nom": inputs.get("nom"),
            "email": user.email if user else None,
            "target_type": redemption.target_type,
            "redeemed_at": redemption.redeemed_at.isoformat(),
            "analysis_id": report.id if report is not None else None,
        })
    return jsonify({"beneficiaires": people}), 200


NOTE_MAX = 20_000


def _my_report(analysis_id: str) -> Analysis | None:
    """An advisor-door report this counselor owns, or None. Another
    counselor's, a candidate's own, or a missing one all answer the same 404."""
    row = db.session.get(Analysis, analysis_id)
    if row is None or row.door != doors.ADVISOR or row.counselor_id != get_jwt_identity():
        return None
    return row


def _code_labels(analysis_ids: list[str]) -> dict[str, str]:
    """Which code each report came through, by its label — how a counselor
    tells reports apart beside prénom and nom (ruling 9)."""
    if not analysis_ids:
        return {}
    rows = (
        db.session.query(CodeRedemption.target_id, CounselorCode.label)
        .join(CounselorCode, CounselorCode.id == CodeRedemption.code_id)
        .filter(CodeRedemption.target_type == "analysis", CodeRedemption.target_id.in_(analysis_ids))
        .all()
    )
    return dict(rows)


_NOT_FOUND = ({"error": "Analyse introuvable."}, 404)


@counselor_space_bp.get("/analyses")
@approved_counselor_required
def my_reports():
    rows = (
        Analysis.query.filter_by(counselor_id=get_jwt_identity(), door=doors.ADVISOR)
        .order_by(Analysis.created_at.desc())
        .all()
    )
    labels = _code_labels([r.id for r in rows])
    return jsonify({"analyses": [
        {
            "id": r.id,
            "prenom": (r.inputs or {}).get("prenom"),
            "nom": (r.inputs or {}).get("nom"),
            "code_label": labels.get(r.id),
            "status": r.status,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]}), 200


@counselor_space_bp.get("/analyses/<analysis_id>")
@approved_counselor_required
def my_report(analysis_id):
    row = _my_report(analysis_id)
    if row is None:
        return jsonify(_NOT_FOUND[0]), _NOT_FOUND[1]
    # A run a restart orphaned reads as the failure it is, so « Relancer » is
    # offered (decision 27).
    reap_if_orphaned(row)
    return jsonify({"analysis": row.to_dict(), "code_label": _code_labels([row.id]).get(row.id)}), 200


@counselor_space_bp.delete("/analyses/<analysis_id>")
@approved_counselor_required
def delete_my_report(analysis_id):
    row = _my_report(analysis_id)
    if row is None:
        return jsonify(_NOT_FOUND[0]), _NOT_FOUND[1]
    # counselor_notes' foreign key has no ON DELETE: the notes go first.
    CounselorNote.query.filter_by(analysis_id=row.id).delete()
    PriceFeedback.query.filter_by(analysis_id=row.id).delete()
    db.session.delete(row)
    db.session.commit()
    return jsonify({"message": "Analyse supprimée."}), 200


@counselor_space_bp.post("/analyses/<analysis_id>/relaunch")
@approved_counselor_required
def relaunch_my_report(analysis_id):
    """« Relancer » (decision 27): the same row, the same inputs, no new code
    use — the candidate left with /analyse/envoyee and cannot retry. Only a
    failed run: a second click while the first is queued is a 409, so one
    failure never becomes two paid runs."""
    row = _my_report(analysis_id)
    if row is None:
        return jsonify(_NOT_FOUND[0]), _NOT_FOUND[1]
    # A conditional update, not read-then-write: two clicks that arrive
    # together both read 'error', and only one of them may start a run.
    claimed = (
        Analysis.query
        .filter(Analysis.id == row.id, Analysis.status.in_(("error", "timeout")))
        .update({"status": "queued", "progress": 0}, synchronize_session=False)
    )
    db.session.commit()
    if claimed != 1:
        return jsonify({"error": "Cette analyse n'a pas besoin d'être relancée."}), 409
    start_analysis(row.id, current_app._get_current_object())
    return jsonify({"analysis": row.to_dict()}), 200


def _my_note(row: Analysis) -> CounselorNote | None:
    return CounselorNote.query.filter_by(analysis_id=row.id, counselor_id=get_jwt_identity()).first()


@counselor_space_bp.get("/analyses/<analysis_id>/notes")
@approved_counselor_required
def my_report_note(analysis_id):
    row = _my_report(analysis_id)
    if row is None:
        return jsonify(_NOT_FOUND[0]), _NOT_FOUND[1]
    note = _my_note(row)
    return jsonify({"note": (note.body or "") if note else ""}), 200


@counselor_space_bp.put("/analyses/<analysis_id>/notes")
@approved_counselor_required
def save_my_report_note(analysis_id):
    row = _my_report(analysis_id)
    if row is None:
        return jsonify(_NOT_FOUND[0]), _NOT_FOUND[1]
    # A body without a string « note » is refused, never read as "": that
    # would clear the stored note and answer 200 — the defect the retired
    # /api/c notes route shipped with (tests/test_malformed_bodies.py, class C).
    # An explicit "" is still the way to clear it.
    data = json_object()
    if not isinstance(data.get("note"), str):
        return jsonify({"error": "Note invalide."}), 400
    body = raw_text_field(data, "note")
    if len(body) > NOTE_MAX:
        return jsonify({"error": "Note trop longue (20 000 caractères maximum)."}), 400
    note = _my_note(row)
    if note is None:
        note = CounselorNote(analysis_id=row.id, counselor_id=get_jwt_identity())
        db.session.add(note)
    note.body = body
    db.session.commit()
    return jsonify({"note": note.body}), 200

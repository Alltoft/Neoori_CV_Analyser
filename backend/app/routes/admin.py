from flask import Blueprint, jsonify, request
from sqlalchemy import func
from datetime import datetime, date, timedelta
from flask_jwt_extended import get_jwt_identity
from ..extensions import db
from ..models.analysis import Analysis
from ..models.user import User
from ..models.prompt_version import PromptVersion
from ..models.counselor_code import CounselorCode
from ..models.counselor_profile import CounselorProfile
from ..models.voyage import STATUS_S0, STATUS_TERMINE, Voyage
from ..services import email_service
from ..services import section_registry as registry
from ..services import tiers
from ..utils.decorators import admin_required
from ..utils.request_body import json_object, text_field

admin_bp = Blueprint("admin", __name__)

# The three values User.role may hold. PUT /users/<id>/role is the only way to
# change one: without it nobody can be made a counselor, and nobody can
# validate a voyage portrait.
ROLES = ("candidate", "counselor", "admin")

# Pricing and model routing live in services/tiers.py so the generation path
# and this dashboard can't drift. Legacy rows store the old model nicknames
# in inputs._tier; tiers.normalize() folds them into plan names.

# Dialect-portable: JSON_UNQUOTE(JSON_EXTRACT(...)) on MySQL, json_extract on SQLite
_TIER_EXPR = Analysis.inputs["_tier"].as_string()


@admin_bp.get("/stats")
@admin_required
def stats():
    """KPI strip data for the admin dashboard."""
    total_analyses = Analysis.query.count()
    success_count = Analysis.query.filter_by(status="success").count()
    error_count = Analysis.query.filter_by(status="error").count()
    timeout_count = Analysis.query.filter_by(status="timeout").count()
    paid_count = User.query.filter_by(plan="paid").count()
    total_users = User.query.count()

    tokens_row = db.session.query(
        func.sum(Analysis.tokens_in).label("total_in"),
        func.sum(Analysis.tokens_out).label("total_out"),
    ).first()
    total_tokens_in = int(tokens_row.total_in or 0)
    total_tokens_out = int(tokens_row.total_out or 0)

    # One active prompt per parcours. This used to be a single unfiltered
    # .first(), which returned whichever row the DB happened to yield.
    active_prompts = PromptVersion.query.filter_by(is_active=True).all()
    by_path = {p.path: p.to_dict(include_text=False) for p in active_prompts}

    voyages = {
        "started": Voyage.query.count(),
        # A voyage past S0 is either s0_termine or termine — the status
        # carries what "0" in sessions_completed says, without a JSON read.
        "s0_done": Voyage.query.filter(Voyage.status.in_((STATUS_S0, STATUS_TERMINE))).count(),
        "completed": Voyage.query.filter_by(status=STATUS_TERMINE).count(),
        "validated": Voyage.query.filter_by(portrait_status="validated").count(),
    }

    return jsonify({
        "total_analyses": total_analyses,
        "success_count": success_count,
        "error_count": error_count,
        "timeout_count": timeout_count,
        "success_rate": round(success_count / total_analyses * 100, 1) if total_analyses else 0,
        "conversion_rate": round(paid_count / total_users * 100, 1) if total_users else 0,
        "total_tokens_in": total_tokens_in,
        "total_tokens_out": total_tokens_out,
        "active_prompts": by_path,
        # Kept so an older frontend build doesn't lose the KPI tile mid-deploy.
        "active_prompt": by_path.get(registry.DEFAULT_PARCOURS),
        "voyages": voyages,
    }), 200


@admin_bp.get("/analyses")
@admin_required
def list_all_analyses():
    """Full analysis log for admin — read only."""
    page = int(request.args.get("page", 1))
    status_filter = request.args.get("status", "").strip()
    search = request.args.get("search", "").strip()
    from_date = request.args.get("from", "").strip()
    to_date = request.args.get("to", "").strip()

    q = Analysis.query

    if status_filter:
        q = q.filter(Analysis.status == status_filter)

    try:
        if from_date:
            q = q.filter(Analysis.created_at >= datetime.fromisoformat(from_date))
        if to_date:
            end = datetime.fromisoformat(to_date) + timedelta(days=1)
            q = q.filter(Analysis.created_at < end)
    except ValueError:
        return jsonify({"error": "Format de date invalide. Utilisez YYYY-MM-DD."}), 400

    if search:
        like = f"%{search}%"
        q = q.filter(
            db.or_(
                func.json_extract(Analysis.inputs, "$.prenom").ilike(like),
                func.json_extract(Analysis.inputs, "$.cible_visee").ilike(like),
            )
        )

    analyses = q.order_by(Analysis.created_at.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    return jsonify({
        "analyses": [a.to_dict() for a in analyses.items],
        "total": analyses.total,
        "pages": analyses.pages,
        "page": analyses.page,
    }), 200


@admin_bp.get("/users")
@admin_required
def list_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify({"users": [u.to_dict() for u in users]}), 200


@admin_bp.put("/users/<user_id>/role")
@admin_required
def set_user_role(user_id):
    """Grant or revoke a role.

    The only way to make a counselor, and therefore the only way anyone can
    ever validate a voyage portrait. Demoting the last admin is refused: it
    locks every admin out of the dashboard, and nothing in the UI recovers
    from that.
    """
    # A JSON body that parses but isn't an object (e.g. a bare array or
    # string) is still truthy, so `... or {}` would let a non-dict through
    # to .get() and raise AttributeError -> an unhandled 500. Normalize
    # explicitly instead.
    data = request.get_json(silent=True)
    data = data if isinstance(data, dict) else {}
    # Same guard as unlock_voyage's "code" and upsert_voyage_note's "body":
    # a non-string "role" (an int, a list, a dict, a bool) must not reach
    # .strip() and raise AttributeError -> an unhandled 500.
    role = data.get("role")
    role = role.strip() if isinstance(role, str) else ""
    if role not in ROLES:
        return jsonify({"error": "Rôle invalide."}), 400

    user = User.query.get_or_404(user_id)
    if user.role == "admin" and role != "admin":
        others = User.query.filter(User.role == "admin", User.id != user.id).count()
        if others == 0:
            return jsonify({
                "error": "Impossible de retirer le dernier rôle administrateur."
            }), 409

    user.role = role
    db.session.commit()
    return jsonify({"user": user.to_dict()}), 200


@admin_bp.get("/counselor-codes")
@admin_required
def list_counselor_codes():
    codes = CounselorCode.query.order_by(CounselorCode.created_at.desc()).all()
    return jsonify({"codes": [c.to_dict() for c in codes]}), 200


@admin_bp.post("/counselor-codes")
@admin_required
def create_counselor_code():
    user_id = get_jwt_identity()
    data = json_object()
    label = text_field(data, "label")
    if not label:
        return jsonify({"error": "label requis."}), 400

    code = CounselorCode(label=label, created_by_id=user_id)
    db.session.add(code)
    db.session.commit()
    return jsonify({"code": code.to_dict()}), 201


@admin_bp.delete("/counselor-codes/<code_id>")
@admin_required
def deactivate_counselor_code(code_id):
    code = CounselorCode.query.get_or_404(code_id)
    code.is_active = False
    db.session.commit()
    return jsonify({"code": code.to_dict()}), 200


def _optional_limit(data: dict, key: str) -> tuple[int | None, str | None]:
    """A nullable positive integer. Absent or null means illimité.

    0 and negatives are refused rather than silently meaning "none": an admin
    typing 0 means "no codes", which is a revocation, not a limit.
    """
    value = data.get(key)
    if value is None:
        return None, None
    if isinstance(value, bool) or not isinstance(value, int):
        return None, f"{key} doit être un entier."
    if value < 1:
        return None, f"{key} doit être supérieur à zéro."
    return value, None


def _decide(profile, status, reason, reviewer_id):
    """Write the decision and keep user.role a function of it.

    approved <=> role 'counselor'. Nothing else may set that role for a
    conseiller: the JWT claim is minted from it, and every counselor guard
    reads the claim.

    An admin's role is never touched. POST /api/counselor/apply already refuses
    a demande from an admin account; this is the second lock on the same door,
    because an unconditional write here would demote an admin out of their own
    dashboard — irreversible through the UI on a single-admin install.
    set_user_role guards the equivalent case at admin.py:155-160.
    """
    profile.status = status
    profile.decision_reason = reason
    profile.reviewed_at = datetime.utcnow()
    profile.reviewed_by_id = reviewer_id
    if profile.user.role != "admin":
        profile.user.role = "counselor" if status == "approved" else "candidate"


@admin_bp.get("/counselor-applications")
@admin_required
def list_counselor_applications():
    query = CounselorProfile.query
    status = request.args.get("status")
    if status:
        query = query.filter(CounselorProfile.status == status)
    rows = query.order_by(CounselorProfile.created_at.desc()).all()
    return jsonify({"applications": [p.to_dict(with_user=True) for p in rows]}), 200


@admin_bp.post("/counselor-applications/<profile_id>/approve")
@admin_required
def approve_counselor_application(profile_id):
    profile = CounselorProfile.query.get_or_404(profile_id)
    if profile.status != "pending":
        return jsonify({"error": "Cette demande a déjà été traitée."}), 409

    data = json_object()
    max_codes, error = _optional_limit(data, "max_codes")
    if error:
        return jsonify({"error": error}), 400
    max_uses, error = _optional_limit(data, "max_uses_per_code")
    if error:
        return jsonify({"error": error}), 400

    profile.max_codes = max_codes
    profile.max_uses_per_code = max_uses
    _decide(profile, "approved", None, get_jwt_identity())
    db.session.commit()

    email_service.send_counselor_approved(profile)
    return jsonify({"application": profile.to_dict(with_user=True)}), 200


@admin_bp.post("/counselor-applications/<profile_id>/reject")
@admin_required
def reject_counselor_application(profile_id):
    profile = CounselorProfile.query.get_or_404(profile_id)
    if profile.status != "pending":
        return jsonify({"error": "Cette demande a déjà été traitée."}), 409

    reason = text_field(json_object(), "reason")
    if not reason:
        return jsonify({"error": "Un motif est requis."}), 400

    _decide(profile, "rejected", reason, get_jwt_identity())
    db.session.commit()

    email_service.send_counselor_rejected(profile)
    return jsonify({"application": profile.to_dict(with_user=True)}), 200


@admin_bp.post("/counselor-applications/<profile_id>/revoke")
@admin_required
def revoke_counselor_application(profile_id):
    """Withdraw access from an approved conseiller.

    'revoked', not 'rejected': one is a demande that failed review, the other a
    conseiller who worked and whose access was withdrawn. Their codes stay
    valid — revoking the person is not the same as burning codes bénéficiaires
    already hold; deactivate those separately if that is what you mean.
    """
    profile = CounselorProfile.query.get_or_404(profile_id)
    if profile.status != "approved":
        return jsonify({"error": "Ce compte n'est pas actif."}), 409

    reason = text_field(json_object(), "reason")
    if not reason:
        return jsonify({"error": "Un motif est requis."}), 400

    _decide(profile, "revoked", reason, get_jwt_identity())
    db.session.commit()
    return jsonify({"application": profile.to_dict(with_user=True)}), 200


@admin_bp.put("/counselor-applications/<profile_id>/limits")
@admin_required
def set_counselor_limits(profile_id):
    profile = CounselorProfile.query.get_or_404(profile_id)
    data = json_object()

    max_codes, error = _optional_limit(data, "max_codes")
    if error:
        return jsonify({"error": error}), 400
    max_uses, error = _optional_limit(data, "max_uses_per_code")
    if error:
        return jsonify({"error": error}), 400

    profile.max_codes = max_codes
    profile.max_uses_per_code = max_uses
    db.session.commit()
    return jsonify({"application": profile.to_dict(with_user=True)}), 200


@admin_bp.get("/stats/timeseries")
@admin_required
def stats_timeseries():
    try:
        days_param = int(request.args.get("days", 30))
    except ValueError:
        return jsonify({"error": "days doit être un entier."}), 400
    if not (1 <= days_param <= 365):
        return jsonify({"error": "days doit être compris entre 1 et 365."}), 400

    today = date.today()
    window_start = datetime.combine(today - timedelta(days=days_param - 1), datetime.min.time())
    window_end = datetime.combine(today + timedelta(days=1), datetime.min.time())

    # Aggregate all analyses in the window grouped by day
    agg_rows = (
        db.session.query(
            func.date(Analysis.created_at).label("day"),
            func.count(Analysis.id).label("cnt"),
            (func.coalesce(func.sum(Analysis.tokens_in), 0)
             + func.coalesce(func.sum(Analysis.tokens_out), 0)).label("tokens"),
        )
        .filter(Analysis.created_at >= window_start, Analysis.created_at < window_end)
        .group_by(func.date(Analysis.created_at))
        .all()
    )

    # Paying tiers (paid + premium) grouped by day
    paid_rows = (
        db.session.query(
            func.date(Analysis.created_at).label("day"),
            func.count(Analysis.id).label("cnt"),
        )
        .filter(
            Analysis.created_at >= window_start,
            Analysis.created_at < window_end,
            db.or_(*[_tier_filter(t) for t in (tiers.PAID, tiers.PREMIUM)]),
        )
        .group_by(func.date(Analysis.created_at))
        .all()
    )

    # Index by date string for O(1) lookup
    agg_by_day = {str(r.day): r for r in agg_rows}
    paid_by_day = {str(r.day): r.cnt for r in paid_rows}

    result = []
    for i in range(days_param - 1, -1, -1):
        d = today - timedelta(days=i)
        day_str = d.isoformat()
        row = agg_by_day.get(day_str)
        count = int(row.cnt) if row else 0
        paid = int(paid_by_day.get(day_str, 0))
        result.append({
            "date": day_str,
            "count": count,
            "tokens": int(row.tokens) if row else 0,
            "free_count": count - paid,
            "paid_count": paid,
        })

    return jsonify({"days": result}), 200


def _tier_filter(tier: str):
    """Match a plan tier, including the nickname legacy rows were written with."""
    aliases = [tier] + [old for old, new in tiers.LEGACY.items() if new == tier]
    clause = _TIER_EXPR.in_(aliases)
    if tier == tiers.FREE:
        # Analyses created before _tier existed bill as free.
        return db.or_(clause, _TIER_EXPR.is_(None))
    return clause


@admin_bp.get("/costs")
@admin_required
def costs():
    try:
        days_param = int(request.args.get("days", 30))
    except ValueError:
        return jsonify({"error": "days doit être un entier."}), 400
    if not (1 <= days_param <= 365):
        return jsonify({"error": "days doit être compris entre 1 et 365."}), 400

    today = date.today()
    window_start = datetime.combine(today - timedelta(days=days_param - 1), datetime.min.time())
    window_end = datetime.combine(today + timedelta(days=1), datetime.min.time())

    # One grouped query per tier, indexed by day.
    by_tier = {}
    for tier in tiers.TIERS:
        rows = (
            db.session.query(
                func.date(Analysis.created_at).label("day"),
                func.count(Analysis.id).label("cnt"),
                func.coalesce(func.sum(Analysis.tokens_in), 0).label("tin"),
                func.coalesce(func.sum(Analysis.tokens_out), 0).label("tout"),
            )
            .filter(
                Analysis.created_at >= window_start,
                Analysis.created_at < window_end,
                _tier_filter(tier),
            )
            .group_by(func.date(Analysis.created_at))
            .all()
        )
        by_tier[tier] = {str(r.day): r for r in rows}

    days = []
    total_cost_usd = 0.0
    totals = {
        "analyses_count": 0,
        "tiers": {t: {"count": 0, "tokens_in": 0, "tokens_out": 0} for t in tiers.TIERS},
    }

    for i in range(days_param - 1, -1, -1):
        day_str = (today - timedelta(days=i)).isoformat()
        day_cost_usd = 0.0
        day_count = 0
        per_tier = {}

        for tier in tiers.TIERS:
            r = by_tier[tier].get(day_str)
            t_in = int(r.tin) if r else 0
            t_out = int(r.tout) if r else 0
            cnt = int(r.cnt) if r else 0

            per_tier[tier] = {"count": cnt, "tokens_in": t_in, "tokens_out": t_out}
            day_cost_usd += tiers.cost_usd(tier, t_in, t_out)
            day_count += cnt

            totals["tiers"][tier]["count"] += cnt
            totals["tiers"][tier]["tokens_in"] += t_in
            totals["tiers"][tier]["tokens_out"] += t_out

        total_cost_usd += day_cost_usd
        totals["analyses_count"] += day_count

        days.append({
            "date": day_str,
            "analyses_count": day_count,
            "tiers": per_tier,
            "cost_eur": round(day_cost_usd * tiers.USD_TO_EUR, 4),
        })

    totals["cost_eur"] = round(total_cost_usd * tiers.USD_TO_EUR, 4)
    return jsonify({
        "days": days,
        "total": totals,
        "pricing": tiers.pricing(),
        "usd_to_eur": tiers.USD_TO_EUR,
    }), 200

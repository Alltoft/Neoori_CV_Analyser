from flask import Blueprint, jsonify, request
from sqlalchemy import func
from datetime import datetime, date, timedelta
from flask_jwt_extended import get_jwt_identity
from ..extensions import db
from ..models.analysis import Analysis
from ..models.user import User
from ..models.prompt_version import PromptVersion
from ..models.counselor_code import CounselorCode
from ..utils.decorators import admin_required

admin_bp = Blueprint("admin", __name__)


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

    active_prompt = PromptVersion.query.filter_by(is_active=True).first()

    return jsonify({
        "total_analyses": total_analyses,
        "success_count": success_count,
        "error_count": error_count,
        "timeout_count": timeout_count,
        "success_rate": round(success_count / total_analyses * 100, 1) if total_analyses else 0,
        "conversion_rate": round(paid_count / total_users * 100, 1) if total_users else 0,
        "total_tokens_in": total_tokens_in,
        "total_tokens_out": total_tokens_out,
        "active_prompt": active_prompt.to_dict(include_text=False) if active_prompt else None,
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


@admin_bp.get("/counselor-codes")
@admin_required
def list_counselor_codes():
    codes = CounselorCode.query.order_by(CounselorCode.created_at.desc()).all()
    return jsonify({"codes": [c.to_dict() for c in codes]}), 200


@admin_bp.post("/counselor-codes")
@admin_required
def create_counselor_code():
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}
    label = (data.get("label") or "").strip()
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

    # Sonnet-tier counts grouped by day
    paid_rows = (
        db.session.query(
            func.date(Analysis.created_at).label("day"),
            func.count(Analysis.id).label("cnt"),
        )
        .filter(
            Analysis.created_at >= window_start,
            Analysis.created_at < window_end,
            func.json_unquote(func.json_extract(Analysis.inputs, "$._tier")) == "sonnet",
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


# Anthropic pricing as of 2026-05 — https://www.anthropic.com/pricing
# Model is determined by inputs._tier ('haiku' or 'sonnet'), not user plan.
_HAIKU_IN  = 0.80    # $/MTok input
_HAIKU_OUT = 4.00    # $/MTok output
_SONNET_IN  = 3.00   # $/MTok input
_SONNET_OUT = 15.00  # $/MTok output
_USD_TO_EUR = 0.92

_TIER_EXPR = func.json_unquote(func.json_extract(Analysis.inputs, "$._tier"))


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

    # Haiku = tier is 'haiku' or not set (analyses created before tier was introduced)
    haiku_rows = (
        db.session.query(
            func.date(Analysis.created_at).label("day"),
            func.count(Analysis.id).label("cnt"),
            func.coalesce(func.sum(Analysis.tokens_in), 0).label("tin"),
            func.coalesce(func.sum(Analysis.tokens_out), 0).label("tout"),
        )
        .filter(
            Analysis.created_at >= window_start,
            Analysis.created_at < window_end,
            db.or_(_TIER_EXPR == "haiku", _TIER_EXPR.is_(None)),
        )
        .group_by(func.date(Analysis.created_at))
        .all()
    )

    # Sonnet = tier is 'sonnet'
    sonnet_rows = (
        db.session.query(
            func.date(Analysis.created_at).label("day"),
            func.count(Analysis.id).label("cnt"),
            func.coalesce(func.sum(Analysis.tokens_in), 0).label("tin"),
            func.coalesce(func.sum(Analysis.tokens_out), 0).label("tout"),
        )
        .filter(
            Analysis.created_at >= window_start,
            Analysis.created_at < window_end,
            _TIER_EXPR == "sonnet",
        )
        .group_by(func.date(Analysis.created_at))
        .all()
    )

    haiku_by_day = {str(r.day): r for r in haiku_rows}
    sonnet_by_day = {str(r.day): r for r in sonnet_rows}

    result = []
    total_cost_usd = 0.0
    totals = dict(analyses_count=0, haiku_tokens_in=0, haiku_tokens_out=0,
                  sonnet_tokens_in=0, sonnet_tokens_out=0)

    for i in range(days_param - 1, -1, -1):
        d = today - timedelta(days=i)
        day_str = d.isoformat()
        h = haiku_by_day.get(day_str)
        s = sonnet_by_day.get(day_str)

        h_in  = int(h.tin)  if h else 0
        h_out = int(h.tout) if h else 0
        s_in  = int(s.tin)  if s else 0
        s_out = int(s.tout) if s else 0
        count = (int(h.cnt) if h else 0) + (int(s.cnt) if s else 0)

        cost_usd = (h_in * _HAIKU_IN + h_out * _HAIKU_OUT
                    + s_in * _SONNET_IN + s_out * _SONNET_OUT) / 1_000_000
        total_cost_usd += cost_usd

        totals["analyses_count"]   += count
        totals["haiku_tokens_in"]  += h_in
        totals["haiku_tokens_out"] += h_out
        totals["sonnet_tokens_in"] += s_in
        totals["sonnet_tokens_out"]+= s_out

        result.append({
            "date": day_str,
            "analyses_count": count,
            "haiku_tokens_in": h_in,
            "haiku_tokens_out": h_out,
            "sonnet_tokens_in": s_in,
            "sonnet_tokens_out": s_out,
            "cost_eur": round(cost_usd * _USD_TO_EUR, 4),
        })

    totals["cost_eur"] = round(total_cost_usd * _USD_TO_EUR, 4)
    return jsonify({"days": result, "total": totals}), 200

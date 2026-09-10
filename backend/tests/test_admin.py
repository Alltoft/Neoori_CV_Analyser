import pytest
from datetime import datetime, timedelta
from app.extensions import db as _db
from app.models.analysis import Analysis
from app.models.counselor_code import CounselorCode


def test_counselor_code_to_dict(app):
    with app.app_context():
        code = CounselorCode(label="Cap Emploi Test")
        _db.session.add(code)
        _db.session.commit()

        d = code.to_dict()
        assert d["label"] == "Cap Emploi Test"
        assert len(d["code"]) == 8
        assert d["is_active"] is True
        assert d["uses_count"] == 0
        assert "id" in d
        assert "created_at" in d


def test_list_counselor_codes_empty(client, admin_headers):
    res = client.get("/api/admin/counselor-codes", headers=admin_headers)
    assert res.status_code == 200
    assert res.get_json()["codes"] == []


def test_create_counselor_code(client, admin_headers):
    res = client.post(
        "/api/admin/counselor-codes",
        json={"label": "Cap Emploi Lyon"},
        headers=admin_headers,
    )
    assert res.status_code == 201
    data = res.get_json()["code"]
    assert len(data["code"]) == 8
    assert data["label"] == "Cap Emploi Lyon"
    assert data["is_active"] is True
    assert data["uses_count"] == 0


def test_create_counselor_code_missing_label(client, admin_headers):
    res = client.post("/api/admin/counselor-codes", json={}, headers=admin_headers)
    assert res.status_code == 400


def test_deactivate_counselor_code(client, admin_headers, app):
    with app.app_context():
        code = CounselorCode(label="Test")
        _db.session.add(code)
        _db.session.commit()
        code_id = code.id

    res = client.delete(f"/api/admin/counselor-codes/{code_id}", headers=admin_headers)
    assert res.status_code == 200

    with app.app_context():
        updated = _db.session.get(CounselorCode, code_id)
        assert updated.is_active is False


def test_deactivate_nonexistent_code(client, admin_headers):
    res = client.delete("/api/admin/counselor-codes/nonexistent", headers=admin_headers)
    assert res.status_code == 404


def _make_analysis(status="success", prenom="Alice", cible="Développeur"):
    a = Analysis(
        status=status,
        inputs={"prenom": prenom, "cible_visee": cible},
    )
    _db.session.add(a)
    _db.session.commit()
    return a.id


def test_analyses_filter_by_status(client, admin_headers, app):
    with app.app_context():
        _make_analysis(status="success")
        _make_analysis(status="error")

    res = client.get("/api/admin/analyses?status=success", headers=admin_headers)
    assert res.status_code == 200
    body = res.get_json()
    assert all(a["status"] == "success" for a in body["analyses"])


def test_analyses_search_by_prenom(client, admin_headers, app):
    with app.app_context():
        _make_analysis(prenom="Alice")
        _make_analysis(prenom="Bob")

    res = client.get("/api/admin/analyses?search=alice", headers=admin_headers)
    assert res.status_code == 200
    body = res.get_json()
    assert len(body["analyses"]) == 1
    assert body["analyses"][0]["inputs"]["prenom"] == "Alice"


def test_analyses_pagination(client, admin_headers, app):
    with app.app_context():
        for i in range(55):
            _make_analysis(prenom=f"User{i}")

    res = client.get("/api/admin/analyses?page=1", headers=admin_headers)
    assert res.status_code == 200
    body = res.get_json()
    assert len(body["analyses"]) == 50
    assert body["pages"] == 2
    assert body["total"] == 55


def test_analyses_filter_by_date_range(client, admin_headers, app):
    with app.app_context():
        today = datetime.utcnow().date()
        yesterday = today - timedelta(days=1)
        tomorrow = today + timedelta(days=1)
        _make_analysis(prenom="Today")

    res = client.get(
        f"/api/admin/analyses?from={today.isoformat()}&to={today.isoformat()}",
        headers=admin_headers,
    )
    assert res.status_code == 200
    body = res.get_json()
    assert len(body["analyses"]) == 1
    assert body["analyses"][0]["inputs"]["prenom"] == "Today"


def test_analyses_invalid_date(client, admin_headers):
    res = client.get("/api/admin/analyses?from=notadate", headers=admin_headers)
    assert res.status_code == 400
    assert "date" in res.get_json()["error"].lower()


def test_stats_timeseries(client, admin_headers):
    res = client.get("/api/admin/stats/timeseries?days=7", headers=admin_headers)
    assert res.status_code == 200
    body = res.get_json()
    assert len(body["days"]) == 7
    day = body["days"][0]
    assert "date" in day
    assert "count" in day
    assert "tokens" in day
    assert "free_count" in day
    assert "paid_count" in day


def test_costs(client, admin_headers):
    res = client.get("/api/admin/costs?days=7", headers=admin_headers)
    assert res.status_code == 200
    body = res.get_json()
    assert len(body["days"]) == 7
    assert "total" in body
    # Pricing is per tier now, not a hardcoded haiku/sonnet pair.
    assert set(body["pricing"]) == {"free", "paid", "premium"}
    day = body["days"][0]
    for key in ("date", "analyses_count", "tiers", "cost_eur"):
        assert key in day
    for tier in ("free", "paid", "premium"):
        assert set(day["tiers"][tier]) == {"count", "tokens_in", "tokens_out"}
        assert set(body["total"]["tiers"][tier]) == {"count", "tokens_in", "tokens_out"}


def test_costs_bills_legacy_nickname_rows(app, client, admin_headers):
    """Rows written before the plan-name migration store 'sonnet' in
    inputs._tier and must still land in the paid bucket, not vanish."""
    from app.models.analysis import Analysis
    from app.extensions import db as _db

    _db.session.add(Analysis(
        inputs={"_tier": "sonnet"}, status="success",
        tokens_in=1_000_000, tokens_out=1_000_000,
    ))
    _db.session.commit()

    body = client.get("/api/admin/costs?days=7", headers=admin_headers).get_json()
    assert body["total"]["tiers"]["paid"]["count"] == 1
    assert body["total"]["tiers"]["paid"]["tokens_in"] == 1_000_000
    # 1M in @ $3 + 1M out @ $15 = $18, converted to EUR
    assert body["total"]["cost_eur"] == round(18.0 * 0.92, 4)


# ── roles ────────────────────────────────────────────────────────────────────

from app.models.user import User  # noqa: E402
from app.models.voyage import STATUS_S0, STATUS_TERMINE, Voyage  # noqa: E402
from datetime import datetime as _dt  # noqa: E402


def _plain_user(email="candidat@test.fr", role="candidate"):
    user = User(email=email, password_hash="x", role=role)
    _db.session.add(user)
    _db.session.commit()
    return user


def test_an_admin_can_grant_the_counselor_role(client, admin_headers, app):
    """Without this nobody can validate a voyage portrait, and the feature
    ships with its last step unreachable."""
    user = _plain_user()
    res = client.put(f"/api/admin/users/{user.id}/role",
                     json={"role": "counselor"}, headers=admin_headers)
    assert res.status_code == 200
    assert res.get_json()["user"]["role"] == "counselor"
    assert _db.session.get(User, user.id).role == "counselor"


def test_an_unknown_role_is_refused(client, admin_headers, app):
    user = _plain_user("autre@test.fr")
    res = client.put(f"/api/admin/users/{user.id}/role",
                     json={"role": "superviseur"}, headers=admin_headers)
    assert res.status_code == 400
    assert res.get_json()["error"] == "Rôle invalide."
    assert _db.session.get(User, user.id).role == "candidate"


def test_an_unknown_user_is_a_404(client, admin_headers):
    assert client.put("/api/admin/users/nobody/role",
                      json={"role": "counselor"}, headers=admin_headers).status_code == 404


def test_a_malformed_user_id_is_a_clean_4xx(client, admin_headers):
    """A String(36) primary key means a garbage id never matches, not a 500."""
    res = client.put("/api/admin/users/!!!not-a-uuid!!!/role",
                     json={"role": "counselor"}, headers=admin_headers)
    assert res.status_code == 404


def test_a_non_dict_json_body_is_a_400_not_a_500(client, admin_headers, app):
    """`request.get_json(silent=True) or {}` would let a truthy list through
    to .get() and raise AttributeError -> 500. Must be a clean 400 instead."""
    user = _plain_user("array-body@test.fr")
    res = client.put(f"/api/admin/users/{user.id}/role",
                     json=[1, 2, 3], headers=admin_headers)
    assert res.status_code == 400
    assert res.get_json()["error"] == "Rôle invalide."
    assert _db.session.get(User, user.id).role == "candidate"


def test_a_non_string_role_field_is_a_400_not_a_500(client, admin_headers, app):
    """`(data.get("role") or "").strip()` crashed on a non-string "role" (an
    int, a list, a dict, a bool all survive `or` as truthy) with
    AttributeError -> an unhandled 500. Must be the same clean 400 as an
    unknown role string, for every one of those shapes."""
    user = _plain_user("non-string-role@test.fr")
    for bad_role in (5, [], {}, True):
        res = client.put(f"/api/admin/users/{user.id}/role",
                         json={"role": bad_role}, headers=admin_headers)
        assert res.status_code == 400
        assert res.get_json()["error"] == "Rôle invalide."
    assert _db.session.get(User, user.id).role == "candidate"


def test_the_last_admin_cannot_demote_itself(client, admin_headers, app):
    """Locking every admin out of the dashboard is not recoverable from the UI."""
    last_admin = User.query.filter_by(role="admin").one()
    res = client.put(f"/api/admin/users/{last_admin.id}/role",
                     json={"role": "candidate"}, headers=admin_headers)
    assert res.status_code == 409
    assert res.get_json()["error"] == "Impossible de retirer le dernier rôle administrateur."
    assert _db.session.get(User, last_admin.id).role == "admin"


def test_an_admin_can_be_demoted_once_another_one_exists(client, admin_headers, app):
    first = User.query.filter_by(role="admin").one()
    _plain_user("admin-2@test.fr", role="admin")
    res = client.put(f"/api/admin/users/{first.id}/role",
                     json={"role": "counselor"}, headers=admin_headers)
    assert res.status_code == 200
    # Status alone would pass on a handler that returns 200 without committing.
    assert res.get_json()["user"]["role"] == "counselor"
    assert _db.session.get(User, first.id).role == "counselor"


def test_the_role_endpoint_is_admin_only(client, app):
    from flask_jwt_extended import create_access_token
    user = _plain_user("pas-admin@test.fr")
    token = create_access_token(identity=str(user.id), additional_claims={"role": "candidate"})
    res = client.put(f"/api/admin/users/{user.id}/role", json={"role": "admin"},
                     headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


def test_the_role_endpoint_rejects_a_counselor_jwt(client, app):
    from flask_jwt_extended import create_access_token
    user = _plain_user("conseiller@test.fr", role="counselor")
    token = create_access_token(identity=str(user.id), additional_claims={"role": "counselor"})
    res = client.put(f"/api/admin/users/{user.id}/role", json={"role": "admin"},
                     headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


# ── voyage KPIs ──────────────────────────────────────────────────────────────

def _voyage_row(user, **overrides):
    fields = {"user_id": user.id, "status": "en_cours", "sessions_completed": [],
              "consent_at": _dt.utcnow(), "consent_version": "voyage-v1",
              "age_attested": True}
    fields.update(overrides)
    row = Voyage(**fields)
    _db.session.add(row)
    _db.session.commit()
    return row


def test_stats_counts_voyages_by_stage(client, admin_headers, app):
    user = _plain_user("kpi@test.fr")
    _voyage_row(user)
    _voyage_row(user, status=STATUS_S0)
    _voyage_row(user, status=STATUS_TERMINE, share_token="kpi-1")
    _voyage_row(user, status=STATUS_TERMINE, share_token="kpi-2",
                portrait_status="validated")

    stats = client.get("/api/admin/stats", headers=admin_headers).get_json()
    assert stats["voyages"] == {"started": 4, "s0_done": 3, "completed": 2, "validated": 1}


def test_stats_reports_zeros_rather_than_omitting_the_block(client, admin_headers):
    stats = client.get("/api/admin/stats", headers=admin_headers).get_json()
    assert stats["voyages"] == {"started": 0, "s0_done": 0, "completed": 0, "validated": 0}

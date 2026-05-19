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
    day = body["days"][0]
    for key in ("date", "analyses_count", "haiku_tokens_in", "haiku_tokens_out",
                "sonnet_tokens_in", "sonnet_tokens_out", "cost_eur"):
        assert key in day

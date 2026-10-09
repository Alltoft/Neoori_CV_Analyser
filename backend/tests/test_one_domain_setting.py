"""DOMAIN is the one URL setting (subdomain split spec, decisions 19, 22
and 32): Stripe's return URLs and the CORS list are built from it, and
nothing reads the settings it replaced."""
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.extensions import db
from app.models.analysis import Analysis
from tests.helpers_doors import bearer, user

APP_DIR = Path(__file__).resolve().parents[1] / "app"


def test_nothing_reads_the_retired_url_settings():
    readers = sorted(
        p.relative_to(APP_DIR).as_posix() for p in APP_DIR.rglob("*.py")
        if re.search(r"APP_URL|FRONTEND_URL|FRONTEND_ORIGINS", p.read_text(encoding="utf-8"))
    )
    assert readers == []


@patch("app.routes.payments._stripe")
def test_stripe_returns_to_cv_whichever_host_paid(stripe_factory, client, app):
    app.config["DOMAIN"] = "neoori.tech"
    stripe = MagicMock()
    stripe.checkout.Session.create.return_value = MagicMock(url="https://stripe.test/s")
    stripe_factory.return_value = stripe
    owner = user()
    analysis = Analysis(user_id=owner.id, door="account", inputs={"_path": "1", "_tier": "free"},
                        status="success", output={"1": {}})
    db.session.add(analysis)
    db.session.commit()
    res = client.post("/api/payments/checkout", json={"analysis_id": analysis.id, "tier": "paid"},
                      headers=bearer(owner), base_url="https://voyage.neoori.tech")
    assert res.status_code == 200
    kwargs = stripe.checkout.Session.create.call_args.kwargs
    assert kwargs["success_url"] == (
        f"https://cv.neoori.tech/analyse/{analysis.id}/debloquer?session_id={{CHECKOUT_SESSION_ID}}"
    )
    assert kwargs["cancel_url"] == f"https://cv.neoori.tech/analyse/{analysis.id}/debloquer?canceled=1"


def test_cors_answers_the_three_origins_only(client):
    for origin in ("https://localhost", "https://cv.localhost", "https://voyage.localhost"):
        res = client.get("/api/health", headers={"Origin": origin})
        assert res.headers.get("Access-Control-Allow-Origin") == origin
    for origin in ("https://attacker.example", "http://localhost:3000", "https://www.localhost"):
        res = client.get("/api/health", headers={"Origin": origin})
        assert "Access-Control-Allow-Origin" not in res.headers


def test_an_auth_refusal_answers_cors_for_the_three_origins_only(client):
    res = client.get("/api/auth/me", headers={"Origin": "https://voyage.localhost"})
    assert res.status_code == 401
    assert res.headers.get("Access-Control-Allow-Origin") == "https://voyage.localhost"
    res = client.get("/api/auth/me", headers={"Origin": "https://attacker.example"})
    assert res.status_code == 401
    assert "Access-Control-Allow-Origin" not in res.headers

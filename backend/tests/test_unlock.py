from unittest.mock import patch

from app.extensions import db
from app.models.analysis import Analysis
from app.models.counselor_code import CounselorCode


def _make_analysis(status="success", path="A", output=None):
    a = Analysis(
        inputs={"_path": path, "_tier": "haiku", "cible_visee": "x"},
        status=status,
        output=output if output is not None else {"1": {"title": "t", "body_markdown": "b", "items": []}},
    )
    db.session.add(a)
    db.session.commit()
    return a


def _make_code(active=True):
    c = CounselorCode(label="Cap Emploi test", is_active=active)
    db.session.add(c)
    db.session.commit()
    return c


@patch("app.services.unlock_service.start_analysis")
def test_unlock_with_valid_code(mock_start, client, app):
    a = _make_analysis()
    c = _make_code()
    r = client.post(f"/api/analyses/{a.id}/unlock", json={"code": c.code})
    assert r.status_code == 200
    db.session.refresh(a)
    assert a.status == "queued"
    assert a.inputs["_tier"] == "paid"
    assert a.unlock_method == "code"
    db.session.refresh(c)
    assert c.uses_count == 1
    mock_start.assert_called_once()


@patch("app.services.unlock_service.start_analysis")
def test_unlock_code_normalisation(mock_start, client, app):
    a = _make_analysis()
    c = _make_code()
    spaced = f" {c.code[:4].lower()}-{c.code[4:]} "
    r = client.post(f"/api/analyses/{a.id}/unlock", json={"code": spaced})
    assert r.status_code == 200


def test_unlock_invalid_code(client, app):
    a = _make_analysis()
    r = client.post(f"/api/analyses/{a.id}/unlock", json={"code": "NOPE1234"})
    assert r.status_code == 400


def test_unlock_inactive_code(client, app):
    a = _make_analysis()
    c = _make_code(active=False)
    r = client.post(f"/api/analyses/{a.id}/unlock", json={"code": c.code})
    assert r.status_code == 400


@patch("app.services.unlock_service.start_analysis")
def test_unlock_already_unlocked(mock_start, client, app):
    a = _make_analysis(output={"1": {}, "5": {}})
    c = _make_code()
    r = client.post(f"/api/analyses/{a.id}/unlock", json={"code": c.code})
    assert r.status_code == 409
    db.session.refresh(c)
    assert c.uses_count == 0
    mock_start.assert_not_called()


def test_unlock_path_b_rejected(client, app):
    a = _make_analysis(path="B")
    c = _make_code()
    r = client.post(f"/api/analyses/{a.id}/unlock", json={"code": c.code})
    assert r.status_code == 409


def test_unlock_draft_rejected(client, app):
    a = _make_analysis(status="draft", output=None)
    c = _make_code()
    r = client.post(f"/api/analyses/{a.id}/unlock", json={"code": c.code})
    assert r.status_code == 409


def test_payments_config_disabled_without_key(client, app, monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    r = client.get("/api/payments/config")
    assert r.status_code == 200
    assert r.get_json()["enabled"] is False


def test_checkout_503_without_key(client, app, monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    a = _make_analysis()
    r = client.post("/api/payments/checkout", json={"analysis_id": a.id})
    assert r.status_code == 503


def test_webhook_503_without_secret(client, app, monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    r = client.post("/api/payments/webhook", data=b"{}")
    assert r.status_code == 503


@patch("app.services.unlock_service.start_analysis")
def test_webhook_unlocks_on_real_stripe_object(mock_start, client, app, monkeypatch):
    """Reproduces the prod path: construct_event returns StripeObjects, not
    plain dicts. Guards against re-introducing dict.get() (unsupported on
    stripe v15 objects → KeyError → 500)."""
    import types
    import stripe
    from app.routes import payments as payments_mod

    a = _make_analysis()
    session = stripe.checkout.Session.construct_from(
        {"id": "cs_test_x", "object": "checkout.session",
         "payment_status": "paid", "metadata": {"analysis_id": a.id}},
        "sk_test",
    )
    event = stripe.Event.construct_from(
        {"id": "evt_x", "type": "checkout.session.completed",
         "data": {"object": session}},
        "sk_test",
    )
    fake = types.SimpleNamespace(
        Webhook=types.SimpleNamespace(construct_event=lambda *a, **k: event)
    )
    monkeypatch.setattr(payments_mod, "_stripe", lambda: fake)
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")

    r = client.post("/api/payments/webhook", data=b"{}",
                    headers={"Stripe-Signature": "t=1,v1=x"})
    assert r.status_code == 200
    db.session.refresh(a)
    assert a.status == "queued"
    assert a.unlock_method == "payment"
    assert a.stripe_session_id == "cs_test_x"
    mock_start.assert_called_once()


# ── premium tier ─────────────────────────────────────────────────────────────

def test_premium_purchase_regenerates_at_the_premium_tier(app, monkeypatch):
    """A premium buyer must get §10 and §11, not just the 9 paid sections."""
    import app.services.unlock_service as svc
    monkeypatch.setattr(svc, "start_analysis", lambda *a, **k: None)

    a = _make_analysis()
    ok, _ = svc.unlock_analysis(a, method="payment", stripe_session_id="cs_x", tier="premium")
    assert ok
    assert a.inputs["_tier"] == "premium"


def test_counselor_code_grants_the_paid_tier(app, monkeypatch):
    import app.services.unlock_service as svc
    monkeypatch.setattr(svc, "start_analysis", lambda *a, **k: None)

    a = _make_analysis()
    ok, _ = svc.unlock_analysis(a, method="code")
    assert ok
    assert a.inputs["_tier"] == "paid"


def test_config_exposes_both_offers(client):
    offers = client.get("/api/payments/config").get_json()["offers"]
    assert set(offers) == {"paid", "premium"}
    # Premium is unpriced by the PM; the default is 2-3x the paid tier and
    # overridable by env var without a deploy.
    assert offers["premium"]["cents"] > offers["paid"]["cents"]

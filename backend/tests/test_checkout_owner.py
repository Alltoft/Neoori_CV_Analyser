"""Checkout and verify belong to the owner, and checkout refuses exactly when
the unlock would (four-doors spec, decision 41)."""
from unittest.mock import MagicMock, patch

import pytest

from app.extensions import db
from app.models.analysis import Analysis
from tests.helpers_doors import bearer, user

STRIPE = "app.routes.payments._stripe"


def _analysis(owner, **fields):
    a = Analysis(user_id=owner.id, door="account", inputs={"_path": "1", "_tier": "free"},
                 **({"status": "success", "output": {"1": {}}} | fields))
    db.session.add(a)
    db.session.commit()
    return a


@patch(STRIPE)
def test_checkout_needs_a_session_and_the_owner(stripe_factory, client, app):
    stripe_factory.return_value = MagicMock()
    owner, other = user(), user("other@test.fr")
    a = _analysis(owner)
    body = {"analysis_id": a.id, "tier": "paid"}
    assert client.post("/api/payments/checkout", json=body).status_code == 401
    assert client.post("/api/payments/checkout", json=body, headers=bearer(other)).status_code == 403
    stripe_factory.return_value.checkout.Session.create.assert_not_called()


@pytest.mark.parametrize("fields", [
    {"status": "error"},
    {"status": "running"},
    {"output": {"1": {}, "5": {}}},          # already Complet: no Premium upgrade either
    {"unlock_method": "code"},
])
@patch(STRIPE)
def test_checkout_refuses_whenever_the_unlock_would(stripe_factory, client, app, fields):
    stripe_factory.return_value = MagicMock()
    owner = user()
    a = _analysis(owner, **fields)
    res = client.post("/api/payments/checkout", json={"analysis_id": a.id, "tier": "premium"},
                      headers=bearer(owner))
    assert res.status_code == 409
    stripe_factory.return_value.checkout.Session.create.assert_not_called()


@patch(STRIPE)
def test_checkout_goes_through_for_the_owners_free_report(stripe_factory, client, app):
    stripe = MagicMock()
    stripe.checkout.Session.create.return_value = MagicMock(url="https://stripe.test/s")
    stripe_factory.return_value = stripe
    owner = user()
    a = _analysis(owner)
    res = client.post("/api/payments/checkout", json={"analysis_id": a.id, "tier": "paid"},
                      headers=bearer(owner))
    assert res.status_code == 200 and res.get_json()["url"] == "https://stripe.test/s"


@patch(STRIPE)
def test_verify_needs_the_owner(stripe_factory, client, app):
    import stripe as stripe_lib

    stripe = MagicMock()
    owner, other = user(), user("other@test.fr")
    a = _analysis(owner)
    # A real StripeObject, as test_unlock.py uses: stripe v15 objects support
    # bracket access and .to_dict(), never .get().
    stripe.checkout.Session.retrieve.return_value = stripe_lib.StripeObject.construct_from(
        {"id": "cs_1", "payment_status": "paid", "metadata": {"analysis_id": a.id, "tier": "paid"}},
        "sk_test",
    )
    stripe_factory.return_value = stripe
    assert client.post("/api/payments/verify", json={"session_id": "cs_1"}).status_code == 401
    assert client.post("/api/payments/verify", json={"session_id": "cs_1"},
                       headers=bearer(other)).status_code == 403


# ── the edges: a report with no owner, the owner's own verify, and a stranger's
# verify, which must change nothing ───────────────────────────────────────────

def _paid_session(analysis, tier="paid"):
    """A paid Checkout Session as stripe v15 returns it (see the test above)."""
    import stripe as stripe_lib

    return stripe_lib.StripeObject.construct_from(
        {"id": "cs_1", "payment_status": "paid",
         "metadata": {"analysis_id": analysis.id, "tier": tier}},
        "sk_test",
    )


@patch(STRIPE)
def test_checkout_refuses_a_report_nobody_owns(stripe_factory, client, app):
    """The 9 € unlock needs an owner (decision 41): a no-login or legacy report
    has nobody to charge, whoever is signed in."""
    stripe_factory.return_value = MagicMock()
    a = Analysis(user_id=None, door="legacy", inputs={"_path": "1", "_tier": "free"},
                 status="success", output={"1": {}})
    db.session.add(a)
    db.session.commit()
    res = client.post("/api/payments/checkout", json={"analysis_id": a.id, "tier": "paid"},
                      headers=bearer(user()))
    assert res.status_code == 403
    stripe_factory.return_value.checkout.Session.create.assert_not_called()


@patch("app.services.unlock_service.start_analysis")
@patch(STRIPE)
def test_verify_unlocks_the_owners_own_report(stripe_factory, mock_start, client, app):
    owner = user()
    a = _analysis(owner)
    stripe = MagicMock()
    stripe.checkout.Session.retrieve.return_value = _paid_session(a, tier="premium")
    stripe_factory.return_value = stripe
    res = client.post("/api/payments/verify", json={"session_id": "cs_1"}, headers=bearer(owner))
    assert res.status_code == 200
    db.session.refresh(a)
    assert (a.status, a.unlock_method, a.stripe_session_id) == ("queued", "payment", "cs_1")
    assert a.inputs["_tier"] == "premium"
    mock_start.assert_called_once()


@patch("app.services.unlock_service.start_analysis")
@patch(STRIPE)
def test_verify_by_another_account_unlocks_nothing(stripe_factory, mock_start, client, app):
    """The 403 comes before the unlock, not after it: a session id replayed by
    a stranger must leave the report exactly as it was and start no run."""
    owner, other = user(), user("other@test.fr")
    a = _analysis(owner)
    stripe = MagicMock()
    stripe.checkout.Session.retrieve.return_value = _paid_session(a)
    stripe_factory.return_value = stripe
    res = client.post("/api/payments/verify", json={"session_id": "cs_1"}, headers=bearer(other))
    assert res.status_code == 403
    db.session.refresh(a)
    assert (a.status, a.unlock_method, a.stripe_session_id) == ("success", None, None)
    assert a.inputs["_tier"] == "free"
    mock_start.assert_not_called()

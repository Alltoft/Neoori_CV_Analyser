"""Stripe one-shot payment (9 € — unlock the full 9-section report).

Flow:
  1. POST /checkout {analysis_id}  → Stripe Checkout Session, browser redirects
  2a. Stripe webhook  POST /webhook (checkout.session.completed) → unlock
  2b. Success URL returns to /debloquer?session_id=… → POST /verify → unlock
      (covers webhook lag on free-tier cold starts; unlock is idempotent)

When STRIPE_SECRET_KEY is absent, /config reports disabled and /checkout
returns 503 — the rest of the app works without payment.
"""
import os

from flask import Blueprint, jsonify, request

from ..extensions import db
from ..models.analysis import Analysis
from ..services.unlock_service import unlock_analysis

payments_bp = Blueprint("payments", __name__)

PRICE_EUR_CENTS = 900


def _stripe():
    """Configured stripe module, or None when no key is set."""
    key = os.getenv("STRIPE_SECRET_KEY")
    if not key:
        return None
    import stripe
    stripe.api_key = key
    return stripe


def _frontend_base() -> str:
    # FRONTEND_URL may be a comma-separated list (CORS config) — take the first
    raw = os.getenv("FRONTEND_URL", "http://localhost:3000")
    return raw.split(",")[0].strip().rstrip("/")


@payments_bp.get("/config")
def config():
    return jsonify({"enabled": bool(os.getenv("STRIPE_SECRET_KEY"))}), 200


@payments_bp.post("/checkout")
def create_checkout():
    stripe = _stripe()
    if stripe is None:
        return jsonify({"error": "Paiement indisponible pour le moment."}), 503

    data = request.get_json(silent=True) or {}
    analysis_id = data.get("analysis_id")
    if not analysis_id:
        return jsonify({"error": "analysis_id requis."}), 400

    analysis = Analysis.query.get_or_404(analysis_id)
    if (analysis.inputs or {}).get("_path") == "B":
        return jsonify({"error": "Le portrait de potentiel est déjà complet."}), 400
    if analysis.unlock_method or "5" in (analysis.output or {}):
        return jsonify({"error": "Cette analyse est déjà débloquée."}), 409
    if analysis.status != "success":
        return jsonify({"error": "L'analyse doit être terminée avant le déblocage."}), 409

    base = _frontend_base()
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": "eur",
                "unit_amount": PRICE_EUR_CENTS,
                "product_data": {
                    "name": "neoori — analyse de CV complète",
                    "description": "Déblocage des 9 sections + CV retravaillé + export conseiller",
                },
            },
            "quantity": 1,
        }],
        metadata={"analysis_id": analysis.id},
        success_url=f"{base}/analyse/{analysis.id}/debloquer?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base}/analyse/{analysis.id}/debloquer?canceled=1",
    )
    return jsonify({"url": session.url}), 200


@payments_bp.post("/verify")
def verify_session():
    """Called by the frontend when Stripe redirects back with session_id.
    Source of truth is Stripe's session state, not the redirect itself."""
    stripe = _stripe()
    if stripe is None:
        return jsonify({"error": "Paiement indisponible pour le moment."}), 503

    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id requis."}), 400

    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except Exception:
        return jsonify({"error": "Session de paiement introuvable."}), 404

    # Bracket access + .to_dict() — stripe v15 objects support neither
    # dict.get() nor dict(obj); .to_dict() yields a plain dict.
    if session["payment_status"] != "paid":
        return jsonify({"error": "Paiement non confirmé."}), 402

    md = session["metadata"]
    analysis_id = (md.to_dict() if md else {}).get("analysis_id")
    analysis = Analysis.query.get_or_404(analysis_id)

    ok, reason = unlock_analysis(analysis, method="payment", stripe_session_id=session["id"])
    if not ok and analysis.stripe_session_id == session.id:
        # Webhook beat us to it — report success, frontend proceeds to polling
        return jsonify({"analysis": analysis.to_dict()}), 200
    if not ok:
        return jsonify({"error": reason}), 409
    return jsonify({"analysis": analysis.to_dict()}), 200


@payments_bp.post("/webhook")
def webhook():
    stripe = _stripe()
    secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if stripe is None or not secret:
        return jsonify({"error": "Webhook non configuré."}), 503

    try:
        event = stripe.Webhook.construct_event(
            request.get_data(),  # raw body — required for signature check
            request.headers.get("Stripe-Signature", ""),
            secret,
        )
    except Exception:
        return jsonify({"error": "Signature invalide."}), 400

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        # Bracket access + .to_dict() — stripe v15 objects support neither
        # dict.get() nor dict(obj); .to_dict() yields a plain dict.
        if session["payment_status"] == "paid":
            md = session["metadata"]
            analysis_id = (md.to_dict() if md else {}).get("analysis_id")
            analysis = Analysis.query.get(analysis_id) if analysis_id else None
            if analysis:
                # Idempotent — duplicate deliveries and verify-first both no-op
                unlock_analysis(analysis, method="payment", stripe_session_id=session["id"])

    return jsonify({"received": True}), 200

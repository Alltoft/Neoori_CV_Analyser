"""POST /api/codes/check — which door a code belongs to, before submit
(four-doors spec). The panel uses it to show the advisor-door notice, or to
send a promo code's holder to sign in. It redeems nothing; nginx's `codes`
zone limits it per address (decision 39)."""
from flask import Blueprint, jsonify

from ..services import code_service
from ..utils.request_body import json_object

codes_bp = Blueprint("codes", __name__)


@codes_bp.post("/check")
def check_code():
    code_str = code_service.normalize(json_object().get("code"))
    if not code_str:
        return jsonify({"error": code_service.REQUIRED}), 400
    code, refusal = code_service.resolve(code_str, "analysis")
    if refusal:
        return jsonify({"error": refusal}), 400
    return jsonify({"kind": code_service.kind(code)}), 200

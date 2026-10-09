"""« Recevoir un lien de connexion »: one link that signs up and signs in
(social sign-in spec, decisions 14–17)."""
from datetime import datetime

from flask import Blueprint, jsonify

from ..extensions import db
from ..models.login_link import LoginLink
from ..services import auth_mail, sign_in
from ..utils import auth_links
from ..utils.request_body import json_object, text_field
# The one place a session opens, where a signed-in person lands, the answer
# every dead link gets, and the one for an address a lookalike account holds.
from .auth import ADDRESS_UNAVAILABLE, _issue_session, _landing, _link_error

auth_link_bp = Blueprint("auth_link", __name__)


@auth_link_bp.post("/email-link")
def send_email_link():
    """The same answer for an address with or without an account: the link
    leaves either way, so it says nothing about who has one."""
    data = json_object()
    email = auth_links.normalise_email(data.get("email"))
    if not auth_links.email_shape_ok(email):
        return jsonify({"error": "Email invalide."}), 400
    # The account OF this address, not whatever row the database's collation
    # files under it: a lookalike row's prénom must not greet the typed
    # address, and its mail clock must not be stamped.
    user = sign_in.account_of(email)
    sent = auth_mail.login_link_if_due(email, user, text_field(data, "next") or None)
    return jsonify({"mail_sent": sent}), 200


@auth_link_bp.post("/email-link/check")
def check_email_link():
    """Is this link alive, and for which address? Never spends it: mail
    scanners open links, and some run the page's scripts (decision 16)."""
    payload, code = _live_link(text_field(json_object(), "token"))
    if code:
        return _link_error(code)
    return jsonify({"email": payload["email"]}), 200


@auth_link_bp.post("/email-link/consume")
def consume_email_link():
    payload, code = _live_link(text_field(json_object(), "token"))
    if code:
        return _link_error(code)
    # Atomic: of two clicks racing, one updates the row and the other finds
    # it used (decision 17).
    claimed = (
        LoginLink.query
        .filter(LoginLink.id == payload["jti"], LoginLink.used_at.is_(None))
        .update({"used_at": datetime.utcnow()}, synchronize_session=False)
    )
    db.session.commit()
    if claimed != 1:
        return _link_error("link_invalid")

    user = sign_in.existing_account(None, None, payload["email"])
    if user is None:
        # An address the database files under a lookalike account is neither
        # entered nor signed up. The link stays spent: it was claimed above.
        if sign_in.address_in_use(payload["email"]):
            return jsonify({"error": ADDRESS_UNAVAILABLE, "code": "address_unavailable"}), 409
        response = jsonify({"signup": True})
        sign_in.set_signup_ticket(
            response, method="email", sub=None, email=payload["email"],
            next_path=payload.get("next"),
        )
        return response, 200
    response = jsonify({"user": user.to_dict(), "next": _landing(user, payload)})
    _issue_session(response, user)
    return response, 200


def _live_link(token):
    """(payload, None) for a signed, unexpired, unused link; else (None, code)."""
    result = auth_links.load_login_token(token)
    if result.error:
        return None, result.error
    payload = result.payload
    if not isinstance(payload.get("jti"), str) or not isinstance(payload.get("email"), str):
        return None, "link_invalid"
    row = db.session.get(LoginLink, payload["jti"])
    if row is None or row.used_at is not None:
        return None, "link_invalid"
    return payload, None

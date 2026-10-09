"""The email sign-in link's single use and its pacing clock (social sign-in
spec, decisions 4, 14 and 17).

A table rather than a column on users: the link also reaches addresses that
have no account yet. It keeps an HMAC of the address
(utils/auth_links.email_hash), never the address itself. Rows older than a
day are purged on every insert (services/auth_mail.login_link_if_due).
"""
from datetime import datetime

from ..extensions import db


class LoginLink(db.Model):
    __tablename__ = "login_links"
    __table_args__ = (
        db.Index("ix_login_links_email_hash_created_at", "email_hash", "created_at"),
    )

    id = db.Column(db.String(36), primary_key=True)   # the token's jti
    email_hash = db.Column(db.CHAR(64), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    used_at = db.Column(db.DateTime, nullable=True)

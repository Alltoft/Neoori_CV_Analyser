"""A Google or Microsoft account that opens a neoori account (social sign-in
spec, decision 2).

One row per (provider, subject): `subject` is the ID token's `sub`, stable for
the life of the provider account. No provider token and no provider address
is kept — users.email stays the one address (decision 25). Apple or
FranceConnect would be a new `provider` value, not a new column.
"""
from datetime import datetime
from uuid import uuid4

from sqlalchemy.dialects import mysql

from ..extensions import db

PROVIDERS = ("google", "microsoft")

# Case matters: Microsoft subjects are base64url, and two that differ only by
# case belong to two different people. MySQL's default collations compare
# case-insensitively, so the column takes the binary one there.
SUBJECT_TYPE = db.String(255).with_variant(
    mysql.VARCHAR(255, collation="utf8mb4_bin"), "mysql"
)


class AuthIdentity(db.Model):
    __tablename__ = "auth_identities"
    __table_args__ = (
        db.UniqueConstraint("provider", "subject", name="uq_auth_identities_provider_subject"),
    )

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = db.Column(
        db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider = db.Column(db.String(16), nullable=False)
    subject = db.Column(SUBJECT_TYPE, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

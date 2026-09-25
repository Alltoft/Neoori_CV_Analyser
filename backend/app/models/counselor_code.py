import secrets
import string
from uuid import uuid4
from datetime import datetime
from ..extensions import db


def _generate_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))


class CounselorCode(db.Model):
    __tablename__ = "counselor_codes"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    code = db.Column(db.String(8), unique=True, nullable=False, default=_generate_code, index=True)
    label = db.Column(db.String(255), nullable=False)
    created_by_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    # Whose budget and dashboard this code belongs to. NULL = admin-minted,
    # which every row that predates comptes conseiller is. created_by_id stays
    # "who pressed the button"; for a conseiller-minted code they are the same.
    owner_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    uses_count = db.Column(db.Integer, nullable=False, default=0)
    # NULL = illimité, on all three. Codes minted by a conseiller default to
    # max_uses=1 and a 90-day expiry at the route; codes that already exist
    # keep NULL and behave exactly as they did.
    max_uses = db.Column(db.Integer, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    revoked_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    created_by = db.relationship("User", foreign_keys=[created_by_id])
    owner = db.relationship("User", foreign_keys=[owner_id])

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "label": self.label,
            "is_active": self.is_active,
            "uses_count": self.uses_count,
            "created_by_id": self.created_by_id,
            "owner_id": self.owner_id,
            "max_uses": self.max_uses,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
            "created_at": self.created_at.isoformat(),
        }

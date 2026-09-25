from uuid import uuid4
from datetime import datetime
from ..extensions import db


# pending  — submitted, not yet reviewed
# approved — user.role is 'counselor' for exactly this status
# rejected — the demande failed review, terminal
# revoked  — was approved, access withdrawn afterwards. Kept apart from
#            'rejected' because they are not the same fact: different message
#            on screen, different line in any report.
STATUSES = ("pending", "approved", "rejected", "revoked")


class CounselorProfile(db.Model):
    """One demande per account. Nothing counselor-shaped lives on `users`:
    to_dict() there is returned on every /auth/me, to every candidate."""

    __tablename__ = "counselor_profiles"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = db.Column(
        db.String(36), db.ForeignKey("users.id"), unique=True, nullable=False, index=True
    )

    structure = db.Column(db.String(255), nullable=False)
    fonction = db.Column(db.String(255), nullable=False)
    telephone = db.Column(db.String(32), nullable=False)
    email_pro = db.Column(db.String(255), nullable=True)
    message = db.Column(db.Text, nullable=True)

    status = db.Column(
        db.Enum(*STATUSES, name="counselor_status"),
        nullable=False,
        default="pending",
        index=True,
    )

    # Both NULL = illimité. The admin's two dials: how many codes, and how many
    # uses any one of them may carry. An account-wide redemption quota would be
    # meaningless once a code is multi-use — spec decision 4.
    max_codes = db.Column(db.Integer, nullable=True)
    max_uses_per_code = db.Column(db.Integer, nullable=True)

    decision_reason = db.Column(db.Text, nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reviewed_by_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Two FKs to the same table, so both relationships must name their column.
    user = db.relationship(
        "User",
        foreign_keys=[user_id],
        backref=db.backref("counselor_profile", uselist=False),
    )
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id])

    def to_dict(self, *, with_user: bool = False) -> dict:
        data = {
            "id": self.id,
            "user_id": self.user_id,
            "structure": self.structure,
            "fonction": self.fonction,
            "telephone": self.telephone,
            "email_pro": self.email_pro,
            "message": self.message,
            "status": self.status,
            "max_codes": self.max_codes,
            "max_uses_per_code": self.max_uses_per_code,
            "decision_reason": self.decision_reason,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "created_at": self.created_at.isoformat(),
        }
        if with_user:
            data["user"] = self.user.to_dict()
        return data

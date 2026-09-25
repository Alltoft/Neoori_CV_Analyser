from uuid import uuid4
from datetime import datetime
from ..extensions import db


class CodeRedemption(db.Model):
    """Who redeemed which code, on what, when.

    CounselorCode.uses_count is an integer and answers none of that; an analysis
    unlock records *that* a code was used (Analysis.unlock_method) but never
    which one. The conseiller dashboard is not derivable without this table.
    """

    __tablename__ = "code_redemptions"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    code_id = db.Column(
        db.String(36), db.ForeignKey("counselor_codes.id"), nullable=False, index=True
    )
    # Nullable on purpose: POST /api/analyses/<id>/unlock carries no auth
    # decorator, so the anonymous flow redeems codes too. ON DELETE SET NULL
    # keeps the count when the person is erased — the row survives, they do not.
    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    target_type = db.Column(
        db.Enum("analysis", "voyage", name="redemption_target"), nullable=False
    )
    target_id = db.Column(db.String(36), nullable=False)
    redeemed_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, index=True
    )

    __table_args__ = (
        # A retried unlock must not double-count.
        db.UniqueConstraint(
            "code_id", "target_type", "target_id", name="uq_code_redemptions_target"
        ),
    )

    code = db.relationship("CounselorCode", foreign_keys=[code_id])
    user = db.relationship("User", foreign_keys=[user_id])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "code_id": self.code_id,
            "user_id": self.user_id,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "redeemed_at": self.redeemed_at.isoformat(),
        }

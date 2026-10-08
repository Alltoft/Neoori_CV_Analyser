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
    # Nullable on purpose: an advisor-door redemption has no account to name,
    # and an erased person (ON DELETE SET NULL) or an erased voyage
    # (DELETE /api/voyage) clears it — the row survives, so the use stays
    # counted. NULLs never collide in the unique keys below.
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
    # This redemption's place in the code's per-kind ceiling, 1..max_uses, or
    # NULL for an unlimited code. The unique key below makes the ceiling the
    # database's to enforce (four-doors spec, decision 23): two requests that
    # both read "0 used" both try slot 1, and only one insert succeeds.
    slot = db.Column(db.Integer, nullable=True)
    redeemed_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, index=True
    )

    __table_args__ = (
        # A retried unlock must not double-count.
        db.UniqueConstraint(
            "code_id", "target_type", "target_id", name="uq_code_redemptions_target"
        ),
        db.UniqueConstraint(
            "code_id", "target_type", "slot", name="uq_code_redemptions_slot"
        ),
        # One promo use per account, atomically. Advisor-door redemptions carry
        # user_id NULL, and NULLs never collide in a unique key.
        db.UniqueConstraint(
            "code_id", "target_type", "user_id", name="uq_code_redemptions_user"
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
            "slot": self.slot,
            "redeemed_at": self.redeemed_at.isoformat(),
        }

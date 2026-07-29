from uuid import uuid4
from datetime import datetime
from ..extensions import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(
        db.Enum("candidate", "counselor", "admin", name="user_role"),
        nullable=False,
        default="candidate",
    )
    plan = db.Column(
        db.Enum("free", "paid", "premium", name="user_plan"),
        nullable=False,
        default="free",
    )
    credits_remaining = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    analyses = db.relationship("Analysis", foreign_keys="Analysis.user_id", backref="user", lazy="dynamic")
    counselor_notes = db.relationship("CounselorNote", backref="counselor", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "role": self.role,
            "plan": self.plan,
            "credits_remaining": self.credits_remaining,
            "created_at": self.created_at.isoformat(),
        }

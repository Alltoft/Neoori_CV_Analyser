from uuid import uuid4
from datetime import datetime
from ..extensions import db


class Analysis(db.Model):
    __tablename__ = "analyses"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True, index=True)
    prompt_version_id = db.Column(db.String(36), db.ForeignKey("prompt_versions.id"), nullable=True)

    status = db.Column(
        db.Enum("draft", "queued", "running", "success", "error", "timeout", name="analysis_status"),
        nullable=False,
        default="draft",
        index=True,
    )

    # The 8 input fields stored as JSON
    inputs = db.Column(db.JSON, nullable=True)

    # Parsed AI output — dict with keys '1' through '9', each a section object
    output = db.Column(db.JSON, nullable=True)

    # Raw text response from Claude, preserved for traceability
    raw_output = db.Column(db.Text, nullable=True)

    tokens_in = db.Column(db.Integer, nullable=True)
    tokens_out = db.Column(db.Integer, nullable=True)

    # Public token for counselor share link: /c/<share_token>
    share_token = db.Column(db.String(64), unique=True, nullable=True, index=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    counselor_notes = db.relationship("CounselorNote", backref="analysis", lazy="dynamic")

    def to_dict(self, audience: str = "candidate"):
        data = {
            "id": self.id,
            "status": self.status,
            "inputs": self.inputs,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "share_token": self.share_token,
            "prompt_version_id": self.prompt_version_id,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

        if self.output:
            if audience == "counselor":
                # Spec rule: same object, different view — sections 1, 4, 5 only
                counselor_sections = {k: v for k, v in self.output.items() if k in ("1", "4", "5")}
                data["output"] = counselor_sections
            else:
                data["output"] = self.output

        return data

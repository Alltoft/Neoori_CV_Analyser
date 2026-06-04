from uuid import uuid4
from datetime import datetime
from ..extensions import db


class PromptVersion(db.Model):
    __tablename__ = "prompt_versions"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    version_label = db.Column(db.String(20), nullable=False)  # e.g. 'v1.3'
    system_prompt_text = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=False, index=True)
    path = db.Column(db.String(1), nullable=False, default='A', server_default='A')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    author = db.relationship("User", foreign_keys=[author_id])
    analyses = db.relationship("Analysis", backref="prompt_version", lazy="dynamic")

    def to_dict(self, include_text: bool = True):
        data = {
            "id": self.id,
            "version_label": self.version_label,
            "path": self.path,
            "is_active": self.is_active,
            "author": self.author.email if self.author else None,
            "created_at": self.created_at.isoformat(),
        }
        if include_text:
            data["system_prompt_text"] = self.system_prompt_text
        return data

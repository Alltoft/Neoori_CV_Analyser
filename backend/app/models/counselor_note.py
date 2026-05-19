from uuid import uuid4
from datetime import datetime
from ..extensions import db


class CounselorNote(db.Model):
    __tablename__ = "counselor_notes"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    analysis_id = db.Column(db.String(36), db.ForeignKey("analyses.id"), nullable=False, index=True)
    counselor_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text, nullable=True)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    def to_dict(self):
        return {
            "id": self.id,
            "analysis_id": self.analysis_id,
            "body": self.body,
            "updated_at": self.updated_at.isoformat(),
        }

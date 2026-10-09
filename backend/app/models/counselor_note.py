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

    # One note per counselor per analysis: the counselor page upserts it.
    __table_args__ = (
        db.UniqueConstraint("analysis_id", "counselor_id", name="uq_counselor_notes_analysis_counselor"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "analysis_id": self.analysis_id,
            "body": self.body,
            "updated_at": self.updated_at.isoformat(),
        }

from uuid import uuid4
from datetime import datetime

from ..extensions import db


class RunLog(db.Model):
    """One row per submitted run, for the daily caps (four-doors spec,
    decision 40).

    Append-only, on purpose: the caps used to be counted from `analyses`, and a
    candidate or a token holder may delete their report — so run, read,
    delete, run again would never reach the cap. Nothing deletes from here but
    the purge, after two days.
    """

    __tablename__ = "run_log"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    door = db.Column(db.String(16), nullable=False)
    # No foreign key: this is a count, not a link, and it never needs the
    # account to still exist.
    user_id = db.Column(db.String(36), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.Index("ix_run_log_door_created_at", "door", "created_at"),
        db.Index("ix_run_log_user_id_created_at", "user_id", "created_at"),
    )

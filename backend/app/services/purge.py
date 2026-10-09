"""flask purge-expired (four-doors spec, decision 46).

Three kinds of rows live on a clock instead of an account, and run_log is a
counter. Nothing else is ever selected: a legacy row, an owned row or a
claimed one is never touched by the daily run.

The rollback mode is the one exception, and it is not a clock: before
downgrading past the four-doors migration, every row the previous image would
serve to anyone holding its id has to go (DOCKER.md, « Rollback »).
"""
from datetime import datetime, timedelta

from flask import current_app
from sqlalchemy import and_

from ..extensions import db
from ..models.analysis import Analysis
from ..models.counselor_note import CounselorNote
from ..models.price_feedback import PriceFeedback
from ..models.run_log import RunLog
from . import doors

RUN_LOG_DAYS = 2


def _held():
    return and_(
        Analysis.status == "draft",
        Analysis.user_id.is_(None),
        Analysis.access_token_hash.isnot(None),
    )


def _unclaimed_anonymous():
    return and_(Analysis.door == doors.ANONYMOUS, Analysis.user_id.is_(None))


def _ids(query) -> list[str]:
    return [row.id for row in query.with_entities(Analysis.id).all()]


def _selection(now: datetime, before_rollback: bool) -> dict[str, list[str]]:
    if before_rollback:
        return {
            "held_drafts": _ids(Analysis.query.filter(_held())),
            "anonymous": _ids(Analysis.query.filter(_unclaimed_anonymous())),
            "advisor": _ids(Analysis.query.filter(Analysis.door == doors.ADVISOR)),
        }
    cfg = current_app.config
    return {
        "held_drafts": _ids(Analysis.query.filter(
            _held(), Analysis.created_at < now - timedelta(hours=cfg["HELD_DRAFT_RETENTION_HOURS"]),
        )),
        "anonymous": _ids(Analysis.query.filter(
            _unclaimed_anonymous(),
            Analysis.created_at < now - timedelta(days=cfg["ANONYMOUS_RETENTION_DAYS"]),
        )),
        "advisor": _ids(Analysis.query.filter(
            Analysis.door == doors.ADVISOR,
            Analysis.created_at < now - timedelta(days=cfg["ADVISOR_RETENTION_DAYS"]),
        )),
    }


def _delete(ids: list[str]) -> None:
    """Notes, price feedback, then the rows: counselor_notes' foreign key has
    no ON DELETE, and price_feedback's cascade is not relied upon."""
    if not ids:
        return
    CounselorNote.query.filter(CounselorNote.analysis_id.in_(ids)).delete(synchronize_session=False)
    PriceFeedback.query.filter(PriceFeedback.analysis_id.in_(ids)).delete(synchronize_session=False)
    Analysis.query.filter(Analysis.id.in_(ids)).delete(synchronize_session=False)


def run(*, apply: bool, before_rollback: bool = False, now: datetime | None = None) -> dict[str, int]:
    """Count, and with apply=True delete, in one transaction. Returns the
    counts per kind."""
    now = now or datetime.utcnow()
    selection = _selection(now, before_rollback)
    counts = {kind: len(ids) for kind, ids in selection.items()}
    old_runs = None
    if not before_rollback:
        old_runs = RunLog.query.filter(RunLog.created_at < now - timedelta(days=RUN_LOG_DAYS))
        counts["run_log"] = old_runs.count()
    if apply:
        try:
            for ids in selection.values():
                _delete(ids)
            if old_runs is not None:
                old_runs.delete(synchronize_session=False)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
    return counts

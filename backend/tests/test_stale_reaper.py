"""The startup reaper must not touch analyses that are still running.

create_app() runs in every process that talks to the database — each gunicorn
worker, `flask db upgrade` on deploy, every seed or admin script. An unfiltered
"reset all running rows to error" therefore fires while candidates are mid-run:
their page flips to "L'analyse n'a pas abouti" and stops polling, even though
the background thread goes on to finish and writes `success` a minute later.
Only rows old enough that no live run could still own them may be reaped.
"""
from datetime import datetime, timedelta

from app import reap_stale_running, STALE_RUN_CUTOFF_MINUTES
from app.extensions import db
from app.models.analysis import Analysis


def _analysis(status: str, age_minutes: int) -> Analysis:
    a = Analysis(
        inputs={"_path": "1"},
        status=status,
        created_at=datetime.utcnow() - timedelta(minutes=age_minutes),
    )
    db.session.add(a)
    return a


def test_reaper_leaves_a_live_run_alone(app):
    live = _analysis("running", age_minutes=1)
    db.session.commit()

    assert reap_stale_running() == 0
    assert live.status == "running"


def test_reaper_resets_a_run_orphaned_by_a_restart(app):
    orphan = _analysis("running", age_minutes=STALE_RUN_CUTOFF_MINUTES + 5)
    db.session.commit()

    assert reap_stale_running() == 1
    db.session.refresh(orphan)
    assert orphan.status == "error"


def test_reaper_only_touches_running_rows(app):
    queued = _analysis("queued", age_minutes=120)
    done = _analysis("success", age_minutes=120)
    db.session.commit()

    reap_stale_running()
    db.session.refresh(queued)
    db.session.refresh(done)
    assert queued.status == "queued"
    assert done.status == "success"

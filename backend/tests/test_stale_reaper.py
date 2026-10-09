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


def test_the_reaper_reads_started_at_not_created_at(app):
    """A counselor's « Relancer » re-runs a row created days ago (four-doors
    spec, decision 47): it must survive a boot while it streams."""
    old, now = datetime.utcnow() - timedelta(days=3), datetime.utcnow()
    relaunched = Analysis(status="running", created_at=old, started_at=now, inputs={})
    stuck = Analysis(status="running", created_at=old, started_at=old, inputs={})
    before_the_column = Analysis(status="running", created_at=old, inputs={})
    db.session.add_all([relaunched, stuck, before_the_column])
    db.session.commit()

    assert reap_stale_running() == 2
    db.session.expire_all()
    assert db.session.get(Analysis, relaunched.id).status == "running"


def test_a_run_commits_started_at_with_running_before_it_streams(app):
    """Both reapers read started_at (above), so _run_analysis must commit it
    with `running`, before the model is called. A relaunched row still
    carries its previous run's started_at until then: without the write, the
    reapers would take a live run for an orphan as soon as it is read."""
    from unittest.mock import MagicMock, patch

    from app.models.prompt_version import PromptVersion
    from app.services import anthropic_service as svc

    db.session.add(PromptVersion(version_label="test", system_prompt_text="x", is_active=True, path="1"))
    days_ago = datetime.utcnow() - timedelta(days=3)
    row = Analysis(status="queued", created_at=days_ago, started_at=days_ago,
                   inputs={"_path": "1", "_tier": "free", "cv_text": "c" * 300, "cible_visee": "t" * 60})
    db.session.add(row)
    db.session.commit()
    row_id = row.id
    seen = {}

    def stream(**_request):
        # The run released its session before calling the model, so this
        # reads what it committed.
        current = db.session.get(Analysis, row_id)
        seen["status"], seen["started_at"] = current.status, current.started_at
        raise RuntimeError("no model in tests")

    client = MagicMock()
    client.messages.stream.side_effect = stream
    before = datetime.utcnow()
    with patch.object(svc, "_get_client", return_value=client):
        svc._run_analysis(row_id, app)

    assert seen["status"] == "running"
    assert seen["started_at"] is not None and seen["started_at"] >= before

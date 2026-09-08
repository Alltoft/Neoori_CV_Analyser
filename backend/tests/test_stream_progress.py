"""Live progress, read off the Anthropic stream.

The waiting screen used to animate a clock — it filled to 95 % in 48 s and then
sat there until the row flipped to 'success'. Measured against the live API with
the production code path, a parcours 1 run takes 84 s on the free tier (4
sections) and 119 s on the paid one (9 sections), so every paid analysis froze
at 95 % for more than a minute. These tests cover the replacement: a percentage
derived from the sections the model has actually opened, published to the row
the frontend already polls.
"""
import json

from app.extensions import db
from app.models.analysis import Analysis
from app.services.anthropic_service import (
    ProgressReporter,
    _section_keys,
    _section_open_re,
    _stream_progress,
)

KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9"]
BUDGET = 28800  # 8000 tokens x _CHARS_PER_TOKEN


def _pct(acc: str, keys=None, budget=BUDGET) -> int:
    keys = keys or KEYS
    return _stream_progress(acc, _section_open_re(keys), len(keys), budget)


def _opened(*keys) -> str:
    """A JSON prefix that has opened each of `keys` in turn."""
    body = "x" * 400
    parts = [f'"{k}": {{"title": "T", "body_markdown": "{body}", "items": []}}' for k in keys]
    return "{" + ", ".join(parts)


# ── _stream_progress ──────────────────────────────────────────────────────────

def test_no_section_open_yet_falls_back_to_the_token_budget():
    """A markdown response (structured output refused) opens no section key.

    Characters against the budget is the only signal left; it must still move,
    and must stay clear of 100 so it can't claim a finished report.
    """
    assert _pct("") == 0
    assert _pct("x" * (BUDGET // 4)) == 25
    assert _pct("x" * BUDGET * 2) == 90


def test_progress_tracks_the_sections_the_model_has_opened():
    one = _pct(_opened("1"))
    three = _pct(_opened("1", "2", "3"))
    seven = _pct(_opened("1", "2", "3", "4", "5", "6", "7"))
    assert one < three < seven
    # Two sections finished out of nine, the third under way: ~22 %+.
    assert 22 <= three <= 33
    assert 66 <= seven <= 78


def test_progress_never_reaches_100_while_streaming():
    """100 % is the row flipping to 'success', never an estimate."""
    assert _pct(_opened(*KEYS)) <= 99
    assert _pct(_opened(*KEYS) + "y" * 50_000) <= 99


def test_a_quoted_key_inside_a_body_is_not_a_new_section():
    """Model output can contain `\\"4\\": {` inside prose. Escaped, so the
    lookbehind rejects it — otherwise the bar would jump on quoted text."""
    honest = _opened("1", "2")
    tricky = honest[:-1] + r' the rule \"4\": {see above}"'
    assert _pct(tricky) == _pct(honest)


def test_fewer_sections_means_bigger_steps():
    """The free tier writes 4 sections, the paid one 9 — same fraction rule."""
    free_keys = ["1", "2", "3", "verdict"]
    assert _pct(_opened("1", "2"), keys=free_keys) > _pct(_opened("1", "2"))


# ── ProgressReporter ──────────────────────────────────────────────────────────

class _Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def _reporter(**kw):
    writes = []
    clock = _Clock()
    reporter = ProgressReporter(
        "an-id", keys=KEYS, budget_chars=BUDGET,
        writer=lambda _id, pct: writes.append(pct),
        clock=clock, **kw,
    )
    return reporter, writes, clock


def test_reporter_throttles_writes_to_one_per_interval():
    """One row update per chunk would be hundreds of writes per analysis."""
    reporter, writes, clock = _reporter(min_interval=2.0)
    reporter.update(_opened("1", "2"))
    assert len(writes) == 1
    reporter.update(_opened("1", "2", "3"))   # same second
    assert len(writes) == 1
    clock.t = 2.5
    reporter.update(_opened("1", "2", "3", "4"))
    assert len(writes) == 2


def test_reporter_never_publishes_a_lower_percentage():
    """The structured-output retry restarts the stream from zero; the bar in
    front of the candidate must not run backwards."""
    reporter, writes, clock = _reporter(min_interval=0)
    reporter.update(_opened("1", "2", "3", "4", "5"))
    clock.t = 10
    reporter.update(_opened("1"))             # retry, back to the top
    assert writes == sorted(writes)
    assert len(writes) == 1


def test_a_failing_write_never_breaks_the_run():
    """A progress write is decoration. It must not take the analysis down."""
    def boom(_id, _pct):
        raise RuntimeError("connection lost")

    reporter = ProgressReporter("an-id", keys=KEYS, budget_chars=BUDGET, writer=boom)
    reporter.update(_opened("1", "2"))        # must not raise


# ── the column the frontend polls ────────────────────────────────────────────

def test_progress_is_exposed_on_the_analysis_payload(app):
    analysis = Analysis(inputs={"_path": "1"}, status="running", progress=42)
    db.session.add(analysis)
    db.session.commit()
    assert analysis.to_dict()["progress"] == 42


def test_a_new_analysis_starts_at_zero_progress(app):
    analysis = Analysis(inputs={"_path": "1"}, status="queued")
    db.session.add(analysis)
    db.session.commit()
    assert analysis.to_dict()["progress"] == 0


def test_unlocking_rewinds_progress_for_the_regeneration(app):
    """Unlock re-queues the *same* row. Left at 100 from the first run, the
    waiting screen would show a full bar for the whole 2-minute regeneration."""
    from unittest.mock import patch
    from app.services.unlock_service import unlock_analysis

    analysis = Analysis(
        inputs={"_path": "1", "_tier": "free"},
        status="success",
        progress=100,
        output={"1": {"title": "t", "body_markdown": "b", "items": []}},
    )
    db.session.add(analysis)
    db.session.commit()

    with patch("app.services.unlock_service.start_analysis"):
        ok, _ = unlock_analysis(analysis, method="code")
    assert ok
    assert analysis.status == "queued"
    assert analysis.to_dict()["progress"] == 0


def test_the_poll_endpoint_returns_progress(app, client):
    analysis = Analysis(inputs={"_path": "1"}, status="running", progress=61)
    db.session.add(analysis)
    db.session.commit()
    res = client.get(f"/api/analyses/{analysis.id}")
    assert res.status_code == 200
    assert json.loads(res.data)["analysis"]["progress"] == 61


# ── wiring: a run publishes while it streams ─────────────────────────────────

def test_a_run_publishes_progress_while_it_streams(app):
    """The whole path: stream chunk → reporter → the polled row.

    The unit tests above cover the arithmetic; this one is here because the
    bug was never in the arithmetic — the waiting screen had nothing to read.
    """
    from unittest.mock import MagicMock, patch
    from app.models.prompt_version import PromptVersion
    from app.services import anthropic_service as svc

    db.session.add(PromptVersion(version_label="test", system_prompt_text="x",
                                 is_active=True, path="1"))
    analysis = Analysis(
        inputs={"_path": "1", "_tier": "paid", "cv_text": "c" * 300,
                "cible_visee": "t" * 60},
        status="queued",
    )
    db.session.add(analysis)
    db.session.commit()
    analysis_id = analysis.id

    chunks = [f'"{k}": {{"title": "T", "body_markdown": "{"b" * 600}", "items": []}},'
              for k in _section_keys("1", "paid")]

    stream = MagicMock()
    stream.__enter__.return_value = stream
    stream.text_stream = iter(["{"] + chunks)
    stream.get_final_message.return_value = MagicMock(
        usage=MagicMock(input_tokens=100, output_tokens=200))
    client = MagicMock()
    client.messages.stream.return_value = stream

    seen = []
    real_publish = svc._publish_progress

    def spy(aid, pct):
        real_publish(aid, pct)
        seen.append((pct, db.session.get(Analysis, aid).progress))

    with patch.object(svc, "_get_client", return_value=client), \
         patch.object(svc, "_publish_progress", spy), \
         patch.object(svc, "_PROGRESS_INTERVAL_S", 0):
        svc._run_analysis(analysis_id, app)

    assert seen, "nothing was published during the stream"
    published = [pct for pct, _ in seen]
    assert published == sorted(published)
    assert max(published) <= 99
    for pct, stored in seen:
        assert stored == pct, "the polled row did not receive the percentage"

    # The run committed from its own app context (Flask-SQLAlchemy scopes the
    # session there); this one still holds the row it created.
    db.session.expire_all()
    row = db.session.get(Analysis, analysis_id)
    assert row.status == "success"
    assert row.to_dict()["progress"] == 100

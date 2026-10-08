"""One-off: delete every trace of parcours 2 and 3 from the database.

Spec: docs/superpowers/specs/2026-10-08-remove-parcours-2-3-design.md,
« Data purge ». Temporary: removed from the repo, with its tests, once the
production purge is confirmed.

    python purge_retired_parcours.py            # dry-run: counts, changes nothing
    python purge_retired_parcours.py --apply    # deletes, in one transaction

Which analyses: those the old section_registry.normalize() sent to parcours 2
or 3 -- an inputs._path of exactly "2" or "3", or any value whose str()
upper-cases to "B" (the old Chemin B, which became parcours 3). Everything that
code read as parcours 1 stays, whatever its _path looks like. Drafts included.

Order, for the foreign keys: counselor notes, price feedback, analyses, then
the prompt versions of slots "2", "3" and "B". A kept analysis that still
points at one of those prompts aborts the run before anything is deleted.
Users and code redemptions are kept (spec, decision 5).
"""
import sys
from collections import Counter
from dataclasses import dataclass, field

from app.extensions import db
from app.models.analysis import Analysis
from app.models.code_redemption import CodeRedemption
from app.models.counselor_note import CounselorNote
from app.models.price_feedback import PriceFeedback
from app.models.prompt_version import PromptVersion

RETIRED_SLOTS = ("2", "3", "B")


class PurgeAborted(Exception):
    """A kept analysis references a prompt version marked for deletion."""


def retired_kind(path) -> str | None:
    """'2', '3' or 'B' when the old normalize() routed `path` to parcours 2
    or 3, else None. It matched an exact '2'/'3' before any coercion, then
    folded str(path).upper() == 'B' onto parcours 3."""
    if isinstance(path, str) and path in ("2", "3"):
        return path
    return "B" if str(path).upper() == "B" else None


@dataclass
class Census:
    analysis_ids: list = field(default_factory=list)
    by_kind: Counter = field(default_factory=Counter)  # (kind, status) -> count
    unlocked: int = 0
    notes: int = 0
    feedback: int = 0
    redemptions_kept: int = 0
    prompts: list = field(default_factory=list)  # PromptVersion rows to delete
    blocking: int = 0  # kept analyses pointing at one of those prompts


def census() -> Census:
    """What a purge would delete, and what it keeps. Changes nothing."""
    c = Census()
    rows = Analysis.query.with_entities(
        Analysis.id, Analysis.inputs, Analysis.status, Analysis.unlock_method
    ).all()
    for row in rows:
        inputs = row.inputs if isinstance(row.inputs, dict) else {}
        kind = retired_kind(inputs.get("_path"))
        if kind is None:
            continue
        c.analysis_ids.append(row.id)
        c.by_kind[(kind, row.status)] += 1
        if row.unlock_method:
            c.unlocked += 1

    ids = c.analysis_ids
    c.notes = CounselorNote.query.filter(CounselorNote.analysis_id.in_(ids)).count()
    c.feedback = PriceFeedback.query.filter(PriceFeedback.analysis_id.in_(ids)).count()
    c.redemptions_kept = CodeRedemption.query.filter(
        CodeRedemption.target_type == "analysis", CodeRedemption.target_id.in_(ids)
    ).count()
    c.prompts = (
        PromptVersion.query.filter(PromptVersion.path.in_(RETIRED_SLOTS))
        .order_by(PromptVersion.path, PromptVersion.created_at)
        .all()
    )
    c.blocking = Analysis.query.filter(
        Analysis.prompt_version_id.in_([p.id for p in c.prompts]),
        Analysis.id.notin_(ids),
    ).count()
    return c


def report(c: Census, out=print) -> None:
    out(f"Analyses to delete: {len(c.analysis_ids)}")
    for (kind, status), n in sorted(c.by_kind.items()):
        out(f"  _path {kind!r} · {status}: {n}")
    out(f"  of which unlocked (paid or code): {c.unlocked}")
    out(f"Counselor notes to delete: {c.notes}")
    out(f"Price feedback rows to delete: {c.feedback}")
    out(f"Code redemptions pointing at them (kept): {c.redemptions_kept}")
    out(f"Prompt versions to delete: {len(c.prompts)}")
    for p in c.prompts:
        state = "active" if p.is_active else "inactive"
        out(f"  path {p.path!r} · {p.version_label} · {state} · {p.created_at:%Y-%m-%d}")
    if c.blocking:
        out(f"BLOCKING: {c.blocking} kept analysis(es) reference one of those prompts.")


def purge(apply: bool = False, out=print) -> Census:
    """Dry-run by default. With apply=True, delete in one transaction and
    return the census taken afterwards — empty when everything went."""
    before = census()
    report(before, out)
    if not apply:
        out("Dry-run: nothing deleted. Run again with --apply to delete.")
        return before
    if before.blocking:
        raise PurgeAborted(
            f"{before.blocking} kept analysis(es) reference a prompt version "
            "marked for deletion. Nothing deleted."
        )
    ids = before.analysis_ids
    prompt_ids = [p.id for p in before.prompts]
    try:
        CounselorNote.query.filter(CounselorNote.analysis_id.in_(ids)).delete(
            synchronize_session=False)
        PriceFeedback.query.filter(PriceFeedback.analysis_id.in_(ids)).delete(
            synchronize_session=False)
        Analysis.query.filter(Analysis.id.in_(ids)).delete(synchronize_session=False)
        PromptVersion.query.filter(PromptVersion.id.in_(prompt_ids)).delete(
            synchronize_session=False)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    after = census()
    out("Deleted. What is left to delete now:")
    report(after, out)
    return after


if __name__ == "__main__":
    from app import create_app

    app = create_app()
    with app.app_context():
        try:
            purge(apply="--apply" in sys.argv[1:])
        except PurgeAborted as exc:
            print(f"ABORTED: {exc}")
            sys.exit(1)

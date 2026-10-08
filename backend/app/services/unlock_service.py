from datetime import datetime
from flask import current_app

from ..extensions import db
from ..models.analysis import Analysis
from . import tiers
from .anthropic_service import start_analysis


def refusal(analysis: Analysis) -> str | None:
    """Why this analysis cannot be unlocked, or None. The one rule checkout
    and unlock_analysis share (four-doors spec, decision 41), so a payment is
    never taken for an unlock that then refuses."""
    if analysis.status in ("queued", "running"):
        return "Une génération est déjà en cours pour cette analyse."
    if analysis.status == "draft":
        return "Cette analyse n'a pas encore été générée."
    if analysis.status != "success":
        return "L'analyse doit être terminée avant le déblocage."
    if analysis.unlock_method or "5" in (analysis.output or {}):
        return "Cette analyse est déjà débloquée."
    return None


def unlock_analysis(
    analysis: Analysis,
    method: str,
    stripe_session_id: str | None = None,
    tier: str | None = None,
) -> tuple[bool, str | None]:
    """Switch an analysis to the paid tier and regenerate the full 9 sections.

    Idempotent: returns (False, reason) when the analysis is already unlocked
    or a regeneration is already in flight. Caller commits are not needed —
    this commits before spawning the generation thread.
    """
    reason = refusal(analysis)
    if reason:
        return False, reason

    inputs = analysis.inputs or {}

    # JSON column: reassign a new dict so SQLAlchemy sees the change
    new_inputs = dict(inputs)
    # Honour what was actually bought: a premium purchase must regenerate
    # with §10 and §11, not just the 9 paid sections. A counselor code
    # (tier=None) grants the paid tier.
    new_inputs["_tier"] = tiers.normalize(tier) if tier else tiers.PAID
    analysis.inputs = new_inputs

    analysis.status = "queued"
    # Same row, second generation: the waiting screen reads `progress`, and a
    # stale 100 from the free run would show a full bar for two minutes.
    analysis.progress = 0
    analysis.unlock_method = method
    analysis.unlocked_at = datetime.utcnow()
    if stripe_session_id:
        analysis.stripe_session_id = stripe_session_id
    db.session.commit()

    start_analysis(analysis.id, current_app._get_current_object())
    return True, None

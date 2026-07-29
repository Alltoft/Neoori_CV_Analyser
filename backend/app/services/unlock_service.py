from datetime import datetime
from flask import current_app

from ..extensions import db
from ..models.analysis import Analysis
from . import section_registry as registry
from .anthropic_service import start_analysis


def unlock_analysis(analysis: Analysis, method: str, stripe_session_id: str | None = None) -> tuple[bool, str | None]:
    """Switch an analysis to the paid tier and regenerate the full 9 sections.

    Idempotent: returns (False, reason) when the analysis is already unlocked
    or a regeneration is already in flight. Caller commits are not needed —
    this commits before spawning the generation thread.
    """
    inputs = analysis.inputs or {}

    if registry.normalize(inputs.get("_path")) == "3":
        return False, "Le portrait de potentiel est déjà complet (pas de version payante)."
    if analysis.status in ("queued", "running"):
        return False, "Une génération est déjà en cours pour cette analyse."
    if analysis.status == "draft":
        return False, "Cette analyse n'a pas encore été générée."
    if analysis.unlock_method or "5" in (analysis.output or {}):
        return False, "Cette analyse est déjà débloquée."

    # JSON column: reassign a new dict so SQLAlchemy sees the change
    new_inputs = dict(inputs)
    new_inputs["_tier"] = "sonnet"
    analysis.inputs = new_inputs

    analysis.status = "queued"
    analysis.unlock_method = method
    analysis.unlocked_at = datetime.utcnow()
    if stripe_session_id:
        analysis.stripe_session_id = stripe_session_id
    db.session.commit()

    start_analysis(analysis.id, current_app._get_current_object())
    return True, None

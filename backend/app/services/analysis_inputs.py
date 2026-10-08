"""What a client may put in an analysis's inputs (four-doors spec, decision 37).

Everything else in a stored `inputs` object is the server's: the parcours
stamp, the tier, the profile and voyage folds. Copying the client's object as
posted let any key through — a `_conditions` line straight into the prompt, or
ten megabytes of anything into a row nobody owns. This keeps three keys, as
trimmed text, inside their caps — _chemin is normalized to A or B and never
unbounded.
"""
from flask import current_app

from ..utils.request_body import text_field

CLIENT_KEYS = ("cv_text", "cible_visee", "_chemin")
CHEMIN_OFFRE = "A"
CHEMIN_DESCRIPTION = "B"


def _thousands(n: int) -> str:
    """40000 -> "40 000", the way the French messages print it."""
    return f"{n:,}".replace(",", " ")


def _normalize_chemin(value) -> str:
    """Coerce to a chemin, defaulting to the offer.

    Analyses written before the chemin was carried have no value, and their
    behaviour was chemin A — direct analysis, no framing note.
    """
    if str(value or "").strip().upper() == CHEMIN_DESCRIPTION:
        return CHEMIN_DESCRIPTION
    return CHEMIN_OFFRE


def clean(raw: dict) -> tuple[dict, list[str]]:
    """The allowed keys as trimmed strings, and the French errors for any
    over its cap. A key the client did not send stays absent, so an empty
    draft stays {}. _chemin is normalized to A or B and does not count against
    any cap."""
    inputs = {}

    # Handle cv_text and cible_visee: trimmed, checked against caps
    for key in ("cv_text", "cible_visee"):
        if key in raw:
            inputs[key] = text_field(raw, key)

    # Handle _chemin: normalized to A or B, unbounded
    if "_chemin" in raw:
        inputs["_chemin"] = _normalize_chemin(raw.get("_chemin"))

    errors = []
    cv_max = current_app.config["CV_TEXT_MAX"]
    if len(inputs.get("cv_text", "")) > cv_max:
        errors.append(f"CV trop long ({_thousands(cv_max)} caractères maximum).")
    cible_max = current_app.config["CIBLE_MAX"]
    if len(inputs.get("cible_visee", "")) > cible_max:
        errors.append(f"Cible visée trop longue ({_thousands(cible_max)} caractères maximum).")
    return inputs, errors

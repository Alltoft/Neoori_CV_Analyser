"""What a client may put in an analysis's inputs (four-doors spec, decision 37).

Everything else in a stored `inputs` object is the server's: the parcours
stamp, the tier, the profile and voyage folds. Copying the client's object as
posted let any key through — a `_conditions` line straight into the prompt, or
ten megabytes of anything into a row nobody owns. This keeps three keys, as
trimmed text, inside their caps.
"""
from flask import current_app

from ..utils.request_body import text_field

CLIENT_KEYS = ("cv_text", "cible_visee", "_chemin")


def _thousands(n: int) -> str:
    """40000 -> "40 000", the way the French messages print it."""
    return f"{n:,}".replace(",", " ")


def clean(raw: dict) -> tuple[dict, list[str]]:
    """The allowed keys as trimmed strings, and the French errors for any
    over its cap. A key the client did not send stays absent, so an empty
    draft stays {}."""
    inputs = {key: text_field(raw, key) for key in CLIENT_KEYS if key in raw}

    errors = []
    cv_max = current_app.config["CV_TEXT_MAX"]
    if len(inputs.get("cv_text", "")) > cv_max:
        errors.append(f"CV trop long ({_thousands(cv_max)} caractères maximum).")
    cible_max = current_app.config["CIBLE_MAX"]
    if len(inputs.get("cible_visee", "")) > cible_max:
        errors.append(f"Cible visée trop longue ({_thousands(cible_max)} caractères maximum).")
    return inputs, errors

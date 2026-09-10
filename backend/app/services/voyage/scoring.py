"""Scoring the voyage — arithmetic only, no model, no I/O.

Deterministic by design. The counselor's paper manual adds columns of points;
this module does the same additions, so the same answers always produce the same
sheet and a correction to a scoring table is a code review, not a re-run.

Scores are never stored. `Voyage.synthesis()` calls `synthesize()` on read, so a
fix to a table takes effect for every voyage at once; the portrait keeps a
snapshot of the sheet it was actually written from, which is what makes an old
portrait explainable after a table changes.

`bank` is the only import. Nothing here mutates it.
"""
from . import bank

STAGE_S0 = "s0"
STAGE_VALIDATED = "validated"
STAGES = (STAGE_S0, STAGE_VALIDATED)

# An axis whose resultant lands in this band is an ambivalence the counselor
# explores in restitution — the manual weights those ×1.5 in the portrait.
TENSION_BAND = (-2, 2)

# An axis carried by a single item is inside the band for everyone: one OUI puts
# it at +1, one NON at -1, and it can never leave. A1 (Mobilité) is that axis.
# Flagging it would print a tension on every sheet ever produced (spec errata 17a).
TENSION_MIN_ITEMS = 2

BIG5_HIGH = 2
BIG5_LOW = -2
LEVEL_HIGH, LEVEL_MID, LEVEL_LOW = "Élevé", "Moyen", "Faible"

# Plain French for the extraversion net. Never the words the leak check bans —
# "introversion" and "extraversion" are trait names and stay on the counselor's
# sheet only.
INTRO_EXTRA = {
    "high": "plutôt tourné(e) vers les autres",
    "mid": "à l'aise dans les deux registres",
    "low": "plutôt tourné(e) vers l'intérieur",
}


# ── Completeness ─────────────────────────────────────────────────────────────

def _answers(responses: dict) -> dict:
    return (responses or {}).get("answers") or {}


def missing_items(responses: dict, n: str) -> list[str]:
    """Item ids of session `n` with no valid answer, in bank order.

    An answer that fails bank.validate_answer counts as missing rather than as
    present-but-wrong: the alternative is scoring a stale letter from a bank
    revision that removed it.
    """
    given = _answers(responses)
    return [
        item_id
        for item_id in bank.item_ids(n)
        if item_id not in given or not bank.validate_answer(item_id, given[item_id])
    ]


def session_complete(responses: dict, n: str) -> bool:
    return not missing_items(responses, n)


def completeness(responses: dict) -> dict[str, bool]:
    return {n: session_complete(responses, n) for n in bank.SESSION_IDS}


def chosen_option(responses: dict, item_id: str) -> dict | None:
    """The option dict the person picked, or None if unanswered or not a scene."""
    value = _answers(responses).get(item_id)
    if not isinstance(value, str):
        return None
    return bank.option(item_id, value)

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


# ── Session 0 — the ten bipolar axes ─────────────────────────────────────────

def score_s0(responses: dict) -> dict | None:
    """The manual's page-1 grid: ten axes, their tensions, and the top three.

    Per item loading on an axis with sign s: OUI contributes +s, NON contributes
    -s. `oui` / `non` count contributing items; `resultant` is the signed sum.
    """
    if not session_complete(responses, "0"):
        return None

    given = _answers(responses)
    axes = {}
    for axis_id, meta in bank.AXES.items():
        loadings = bank.axis_items(axis_id)
        oui = sum(1 for item_id, _ in loadings if given[item_id] is True)
        non = len(loadings) - oui
        resultant = sum(
            sign if given[item_id] is True else -sign for item_id, sign in loadings
        )
        axes[axis_id] = {
            "oui": oui,
            "non": non,
            "resultant": resultant,
            "n_items": len(loadings),
            "tension": (
                TENSION_BAND[0] <= resultant <= TENSION_BAND[1]
                and len(loadings) >= TENSION_MIN_ITEMS
            ),
        }

    tensions = [
        {
            "axis": axis_id,
            "resultant": entry["resultant"],
            "label": bank.AXES[axis_id]["label"],
            "tension": bank.AXES[axis_id]["tension"],
        }
        for axis_id, entry in axes.items()
        if entry["tension"]
    ]
    tensions.sort(key=lambda t: int(t["axis"][1:]))

    ranked = [
        (axis_id, entry["resultant"])
        for axis_id, entry in axes.items()
        if entry["resultant"] != 0
    ]
    ranked.sort(key=lambda pair: (-abs(pair[1]), int(pair[0][1:])))
    top3 = []
    for axis_id, resultant in ranked[:3]:
        pole = "pos" if resultant > 0 else "neg"
        meta = bank.AXES[axis_id]
        top3.append({
            "axis": axis_id,
            "resultant": resultant,
            "pole": pole,
            "label": meta[pole],
            "plain": meta[f"plain_{pole}"],
        })

    return {"axes": axes, "tensions": tensions, "top3": top3}


# ── Session 1 — RIASEC ───────────────────────────────────────────────────────

def score_riasec(responses: dict) -> dict | None:
    """Holland letters, summed over the six childhood scenes.

    Normalised because the letters have different ceilings: R can reach 12 and C
    only 9, so a raw 9 means "at the top" for C and "three short" for R. `top3`
    therefore ranks on the ratio, never on the raw score.
    """
    if not session_complete(responses, "1"):
        return None

    scores = {letter: 0 for letter in bank.RIASEC_LETTERS}
    for item_id in bank.item_ids("1"):
        option = chosen_option(responses, item_id)
        for letter, points in (option.get("riasec") or {}).items():
            scores[letter] += points

    maxima = bank.riasec_maxima()
    normalized = {
        letter: round(scores[letter] / maxima[letter], 3) if maxima[letter] else 0.0
        for letter in bank.RIASEC_LETTERS
    }

    ranked = sorted(
        bank.RIASEC_LETTERS,
        key=lambda letter: (-normalized[letter], bank.RIASEC_LETTERS.index(letter)),
    )
    top3 = [
        {
            "letter": letter,
            "univers": bank.RIASEC_UNIVERS[letter],
            "score": scores[letter],
            "normalized": normalized[letter],
        }
        for letter in ranked[:3]
    ]

    return {"scores": scores, "maxima": maxima, "normalized": normalized, "top3": top3}

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

# Maps _level()'s three buckets onto INTRO_EXTRA's registers, so score_s3 reads
# the extraversion bucket off `levels` instead of re-deriving it against
# BIG5_HIGH/BIG5_LOW — _level() stays the one place those thresholds are applied.
_LEVEL_TO_REGISTER = {LEVEL_HIGH: "high", LEVEL_MID: "mid", LEVEL_LOW: "low"}


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
    """The option dict the person picked, or None if unanswered or not a scene.

    A live reference into the bank, not a copy — do not mutate it. Use
    bank.public() if you need a safe copy.
    """
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
    for axis_id in bank.AXES:
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


# ── Session 2 — needs (SDT) and values (Schwartz) ────────────────────────────

def _dominant(counts: dict, order) -> list[str]:
    """Every key holding the maximum, in `order`. A list, not a winner.

    The manual names no tie-break, and a counselor reads this aloud: picking one
    of two equals by dict order would put a value in someone's mouth.
    """
    if not counts:
        return []
    top = max(counts.values())
    if top == 0:
        return []
    return [key for key in order if counts.get(key, 0) == top]


def score_s2(responses: dict) -> dict | None:
    """The manual's Session 2 synthesis box, counted over S2-1..S2-7 only."""
    if not session_complete(responses, "2"):
        return None

    sdt = {need: 0 for need in bank.SDT}
    schwartz = {value: 0 for value in bank.SCHWARTZ}
    for item_id in bank.item_ids("2"):
        option = chosen_option(responses, item_id)
        if option.get("sdt"):
            sdt[option["sdt"]] += 1
        for value in option.get("schwartz") or []:
            schwartz[value] += 1

    probe = chosen_option(responses, "S2-7")
    return {
        "sdt": sdt,
        "sdt_dominant": _dominant(sdt, bank.SDT),
        "schwartz": schwartz,
        "schwartz_dominant": _dominant(schwartz, bank.SCHWARTZ),
        "ambivalences": {
            "item_id": "S2-7",
            "letter": probe["letter"],
            "label": probe["label"],
            "plain": probe["plain"],
        },
    }


# ── Session 3 — Big Five and cognitive style ─────────────────────────────────

def _level(net: int) -> str:
    if net >= BIG5_HIGH:
        return LEVEL_HIGH
    if net <= BIG5_LOW:
        return LEVEL_LOW
    return LEVEL_MID


def score_s3(responses: dict) -> dict | None:
    """The manual's Big Five box, counted over S3-1..S3-7 only.

    Nets, not counts: the manual's « Faible Névrotisme » is a -1 on the same
    trait as « Névrotisme », so reading either as a plain count would score an
    unusually steady person as an unusually anxious one.
    """
    if not session_complete(responses, "3"):
        return None

    big5 = {trait: 0 for trait in bank.BIG5}
    style = {name: 0 for name in bank.STYLES}
    for item_id in bank.item_ids("3"):
        option = chosen_option(responses, item_id)
        for trait, sign in (option.get("big5") or {}).items():
            big5[trait] += sign
        if option.get("style"):
            style[option["style"]] += 1

    levels = {trait: _level(net) for trait, net in big5.items()}

    return {
        "big5": big5,
        "levels": levels,
        "style": style,
        "style_dominant": _dominant(style, bank.STYLES),
        "intro_extra": INTRO_EXTRA[_LEVEL_TO_REGISTER[levels["extraversion"]]],
    }


# ── Session 4 — the environment ──────────────────────────────────────────────

def score_s4(responses: dict) -> dict | None:
    """Six labels, by scene position. No arithmetic — S4 is a preference, not a
    score, and averaging preferences would say nothing."""
    if not session_complete(responses, "4"):
        return None
    return {
        slot: chosen_option(responses, item_id)["env"]
        for slot, item_id in zip(bank.S4_SLOTS, bank.item_ids("4"))
    }


# ── Session 5 — risk and meaning ─────────────────────────────────────────────

def score_s5(responses: dict) -> dict | None:
    """Risk appetite and the meaning signals.

    S5-1/2/3 all speak to risk and the manual names no way to combine them, so
    the three labels stay side by side rather than collapsing into one score the
    paper sheet never produced.
    """
    if not session_complete(responses, "5"):
        return None

    def tag(item_id: str, key: str) -> str:
        return chosen_option(responses, item_id)[key]

    return {
        "risque": tag("S5-1", "risk"),
        "rapport_echec": tag("S5-2", "risk"),
        "rapport_flou": tag("S5-3", "risk"),
        "valeur_centrale": tag("S5-4", "sens"),
        "trace": tag("S5-5", "sens"),
        "sacrifice": tag("S5-6", "sens"),
        "vivant": tag("S5-7", "sens"),
    }


# ── The synthesis sheet ──────────────────────────────────────────────────────

def synthesize(responses: dict) -> dict:
    """The counselor manual's page-18 sheet, assembled from the answers.

    Never None: a voyage that has only finished session 0 still has a sheet, and
    a caller should read `completeness` rather than probe for a missing key. The
    session-1 section is keyed `riasec` because that is what it contains — the
    other five keep their session number since no single framework names them.
    """
    return {
        "scoring_version": bank.SCORING_VERSION,
        "s0": score_s0(responses),
        "riasec": score_riasec(responses),
        "s2": score_s2(responses),
        "s3": score_s3(responses),
        "s4": score_s4(responses),
        "s5": score_s5(responses),
        "completeness": completeness(responses),
    }


# ── The reduced block that reaches an analysis ───────────────────────────────

def _line(label: str, value) -> str | None:
    """A labelled line, or None when there is nothing to say.

    Never prints a label with an empty value: a bare « Besoin dominant : » in
    the prompt invites the model to fill the blank.
    """
    if isinstance(value, (list, tuple)):
        # Same fail-soft rule as the scalar path below: a non-string element
        # is dropped rather than raising TypeError on join().
        value = ", ".join(v for v in value if isinstance(v, str) and v)
    text = (value or "").strip() if isinstance(value, str) else ""
    return f"{label} : {text}" if text else None


def prompt_context(synthesis: dict, micro_phrase: str | None, stage: str) -> list[str]:
    """The plain-French lines stored as Analysis.inputs["_voyage"].

    Content lines only — anthropic_service._voyage_block() adds the
    "--- ... ---" header, exactly as _conditions_block() does for bloc 5.

    Pure over `synthesis`: every string it can emit is already in that dict, and
    it never reaches back into the bank. That is what makes "no numbers, no
    framework words" a testable property rather than a promise.

    Two stages, and the distinction is load-bearing. Before a counselor has
    validated the portrait, an analysis receives only the phrase and the
    session-0 attractions — the person has not been restituted yet, and a report
    must not tell them what the counselor hasn't. An unrecognised stage is
    treated as s0: this fails closed.

    Note for phase 3: "Phrase révélée" shares a root with "révélation", which is
    on the candidate-facing banned-copy list. That ban does not reach this
    label because it is model-facing prompt text, not UI copy — but the
    candidate-facing hub must not reuse this wording as its label for the
    phrase.
    """
    synthesis = synthesis or {}
    lines = [_line("Phrase révélée", micro_phrase)]

    s0 = synthesis.get("s0") or {}
    lines.append(_line(
        "Ce qui l'attire le plus dans dix ans",
        [entry["plain"] for entry in s0.get("top3") or []],
    ))

    if stage == STAGE_VALIDATED:
        riasec = synthesis.get("riasec") or {}
        s2 = synthesis.get("s2") or {}
        s4 = synthesis.get("s4") or {}
        s5 = synthesis.get("s5") or {}
        lines.append(_line(
            "Univers dominants",
            [entry["univers"] for entry in riasec.get("top3") or []],
        ))
        lines.append(_line("Besoin dominant", s2.get("sdt_dominant") or []))
        lines.append(_line(
            "Ambivalences relevées",
            " · ".join(t["tension"] for t in s0.get("tensions") or []),
        ))
        lines.append(_line(
            "Cadre où elle donne le meilleur",
            " · ".join(
                v for v in (s4.get("espace"), s4.get("rythme"), s4.get("equipe")) if v
            ),
        ))
        lines.append(_line("Ce qui l'épuise", s4.get("irritant")))
        lines.append(_line("Ce qui la met en colère", s5.get("valeur_centrale")))
        lines.append(_line("Se sent vivant(e) quand", s5.get("vivant")))

    return [line for line in lines if line]

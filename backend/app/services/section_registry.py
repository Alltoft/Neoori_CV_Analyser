"""Single source of truth for report structure, per parcours.

Replaces the hardcoded "1".."9" model that was spread across the schema
builder, the markdown fallback parser, the counselor filter, and five
places in the frontend.

Three things every consumer needs, and none of them should be derived by
sorting keys:

  * **Order** — list position is the order. Parcours 2 uses letter keys
    (A..G) and parcours 3 Roman numerals (I..VI); neither sorts
    numerically, and `Number("A") - Number("B")` is NaN, which leaves a
    JS sort in insertion order without raising.
  * **Render mode** — "tags" sections render as a tag cloud rather than
    markdown. This used to be a literal `n === "3"` branch.
  * **Tier** — which plans include the section. Enforced by the JSON
    output schema alone; there is no prose instruction telling the model
    which sections to skip.

Section content and tone live in the DB-held system prompt, never here.
This module only describes the shape the model must fill.
"""

FREE = "free"
PAID = "paid"
PREMIUM = "premium"

ALL_TIERS = (FREE, PAID, PREMIUM)
PAID_UP = (PAID, PREMIUM)
PREMIUM_ONLY = (PREMIUM,)

MARKDOWN = "markdown"
TAGS = "tags"


def _s(key, title, tiers=ALL_TIERS, render=MARKDOWN):
    return {"key": key, "title": title, "tiers": tiers, "render": render}


# ── Parcours 1 — « J'ai une cible » ──────────────────────────────────────────
# CV + target. Free tier is §1, §2 (max 3 forces), §3 (max 5 tags) plus a
# verdict that quantifies the frictions without naming them (CDC §4).
# Note this is narrower than the pre-v1.2 free tier, which included §4.
_P1 = [
    _s("1", "Lecture stratégique du parcours"),
    _s("2", "Forces du profil pour la cible"),
    _s("3", "Compétences transférables", render=TAGS),
    _s("verdict", "Verdict", tiers=(FREE,)),
    _s("4", "Ce qui reste à renforcer", tiers=PAID_UP),
    _s("5", "Préconisations terrain", tiers=PAID_UP),
    _s("6", "Exemple de réécriture", tiers=PAID_UP),
    _s("7", "Synthèse pour le candidat", tiers=PAID_UP),
    _s("8", "Pistes d'évolution", tiers=PAID_UP),
    _s("9", "Proposition de CV retravaillé", tiers=PAID_UP),
    _s("10", "Préparation à l'entretien", tiers=PREMIUM_ONLY),
    _s("11", "Questions difficiles", tiers=PREMIUM_ONLY),
]

# ── Parcours 2 — « Je cherche ma direction » ─────────────────────────────────
# CV in hand, no target. Free tier is capital + transferable skills + two
# leads without scenarios, plus a verdict inviting a cadrage meeting.
_P2 = [
    _s("A", "Capital professionnel"),
    _s("C", "Compétences transférables", render=TAGS),
    _s("D", "Pistes hiérarchisées"),
    _s("verdict", "Verdict", tiers=(FREE,)),
    _s("B", "Ce qui ne convient plus", tiers=PAID_UP),
    _s("E", "Scénarios de transition", tiers=PAID_UP),
    _s("F", "Questions pour l'entretien de cadrage", tiers=PAID_UP),
    _s("G", "Proto-CV générique", tiers=PAID_UP),
]

# ── Parcours 3 — « Je pars de zéro » ─────────────────────────────────────────
# No CV. Five life questions in, a CV draft out. Free tier is life capital +
# identified skills + two accessible leads, plus a verdict (direct access or
# training needed).
_P3 = [
    _s("I", "Capital de vie"),
    _s("II", "Compétences identifiées", render=TAGS),
    _s("III", "Pistes métier accessibles"),
    _s("verdict", "Verdict", tiers=(FREE,)),
    _s("IV", "Parcours de transition", tiers=PAID_UP),
    _s("V", "Dispositifs d'accès", tiers=PAID_UP),
    _s("VI", "Ébauche de CV", tiers=PAID_UP),
]


# `counselor` is the 5-minute synthesis a Cap Emploi / Mission Locale
# counselor sees at /c/<share_token>. Parcours 1's set is fixed by the spec
# (§1, §4, §5); parcours 2 and 3 are not specified, so these pick the
# equivalent triple — where the person stands, what no longer fits, and what
# to raise in the meeting.
PARCOURS = {
    "1": {
        "label": "J'ai une cible",
        "sections": _P1,
        "counselor": ("1", "4", "5"),
    },
    "2": {
        "label": "Je cherche ma direction",
        "sections": _P2,
        "counselor": ("A", "B", "F"),
    },
    "3": {
        "label": "Je pars de zéro",
        "sections": _P3,
        "counselor": ("I", "III", "V"),
    },
}

DEFAULT_PARCOURS = "1"


def is_valid(parcours: str) -> bool:
    return parcours in PARCOURS


def normalize(parcours) -> str:
    """Coerce a parcours id to a known value.

    Accepts the legacy 'A'/'B' path codes so rows written before the
    3-parcours migration keep rendering.
    """
    if parcours in PARCOURS:
        return parcours
    legacy = {"A": "1", "B": "3"}
    return legacy.get(str(parcours).upper(), DEFAULT_PARCOURS)


def sections(parcours: str, tier: str | None = None) -> list[dict]:
    """Ordered sections for a parcours, optionally filtered to one tier."""
    all_sections = PARCOURS[normalize(parcours)]["sections"]
    if tier is None:
        return list(all_sections)
    return [s for s in all_sections if tier in s["tiers"]]


def section_keys(parcours: str, tier: str | None = None) -> list[str]:
    return [s["key"] for s in sections(parcours, tier)]


def titles(parcours: str) -> dict[str, str]:
    """key → title, for resolving titles the model didn't return."""
    return {s["key"]: s["title"] for s in sections(parcours)}


def counselor_keys(parcours: str) -> tuple[str, ...]:
    return PARCOURS[normalize(parcours)]["counselor"]


def sections_meta(parcours: str, tier: str | None = None) -> list[dict]:
    """Render instructions for the frontend.

    Shipped on `Analysis.to_dict()` so the report page never has to sort
    keys or guess a title. Order here is the order on the page.
    """
    return [
        {
            "key": s["key"],
            "title": s["title"],
            "render": s["render"],
            "tiers": list(s["tiers"]),
        }
        for s in sections(parcours, tier)
    ]

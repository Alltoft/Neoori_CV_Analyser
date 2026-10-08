"""Single source of truth for report structure, per parcours.

Replaces the hardcoded "1".."9" model that was spread across the schema
builder, the markdown fallback parser, the counselor filter, and five
places in the frontend.

Three things every consumer needs, and none of them should be derived by
sorting keys:

  * **Order** — list position is the order. The free-tier "verdict" sits
    between §3 and §4, and a string sort puts "10" and "11" before "2",
    so no consumer may sort keys.
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


# `counselor` is the 5-minute synthesis a Cap Emploi / Mission Locale
# counselor sees at /c/<share_token>, fixed by the spec (§1, §4, §5).
# Parcours 2 and 3 were retired on 2026-10-08; the dict keeps its shape.
PARCOURS = {
    "1": {
        "label": "J'ai une cible",
        "sections": _P1,
        "counselor": ("1", "4", "5"),
    },
}

DEFAULT_PARCOURS = "1"


def is_valid(parcours: str) -> bool:
    return parcours in PARCOURS


def normalize(parcours) -> str:
    """Coerce a stored parcours id to a known value.

    Accepts the legacy 'A' path code so rows written before the 3-parcours
    migration keep rendering; anything else — a retired '2', '3' or 'B'
    waiting for the purge, or garbage — falls back to parcours 1.
    `parcours in PARCOURS` needs a hashable value; a hostile value (a list,
    a dict) raised TypeError -- an unhandled 500.
    """
    try:
        if parcours in PARCOURS:
            return parcours
    except TypeError:
        pass  # unhashable (a list, a dict) -- never a valid parcours id
    legacy = {"A": "1"}
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

"""The voyage's question bank — text and weights in one place.

Six sessions, 53 scored items. Every item's French text is transcribed verbatim
from `neoori_cahier_papier.pdf`; every option's scoring tags come from the
counselor manual `neoori_scoring_restitution-1.pdf`.

Text and weights live together on purpose. They were authored together on paper
and they drift apart the moment they are split: an option whose wording is edited
in one file and whose points sit in another is a silent scoring bug. `public()`
is what keeps the weights server-side — it strips them, so the API can serve this
same structure without leaking the mapping the product is built on.

Pure data plus lookups. No DB, no I/O, no Flask import.
"""

SCORING_VERSION = "cahier-2026-09"

SESSION_IDS = ("0", "1", "2", "3", "4", "5")

KIND_CHECKLIST = "checklist"
KIND_SCENES = "scenes"

# Every key that carries a weight or an interpretation.
TAG_KEYS = ("riasec", "axes", "sdt", "schwartz", "big5", "style", "env", "risk", "sens")

# `plain` is the prompt-facing paraphrase of an option. It is not a weight, but it
# is not for the browser either — it is written for the model, in a register the
# UI never uses. public() strips it with the rest.
PUBLIC_STRIP = TAG_KEYS + ("plain",)

# Tie-break order for RIASEC, in this order.
RIASEC_LETTERS = ("R", "I", "A", "S", "E", "C")

RIASEC_UNIVERS = {
    "R": "Réaliste",
    "I": "Investigateur",
    "A": "Artistique",
    "S": "Social",
    "E": "Entreprenant",
    "C": "Conventionnel",
}

SDT = ("autonomie", "appartenance", "competence")

# Exactly the eleven values the counselor manual's Dimension column uses. Two of
# them — conservation, integrite — are not canonical Schwartz basic values; they
# are the manual's own vocabulary and the counselor sheet has to match the paper
# it replaces. A twelfth value appearing here is a bank bug.
SCHWARTZ = (
    "autodirection", "stimulation", "hedonisme", "reussite", "pouvoir", "securite",
    "conformite", "bienveillance", "universalisme", "integrite", "conservation",
)

BIG5 = ("ouverture", "conscienciosite", "extraversion", "agreabilite", "nevrotisme")

STYLES = ("holistique", "sequentiel", "adaptatif", "consultatif")

# What the prompt is allowed to say instead of the tag.
STYLE_PLAIN = {
    "holistique": "part de l'ensemble et improvise",
    "sequentiel": "avance par étapes structurées",
    "adaptatif": "ajuste sa méthode au contexte",
    "consultatif": "s'appuie sur les autres pour décider",
}

# S5-1 only. The manual's own casing.
RISK_LEVELS = ("Fort", "Modéré", "Calculé", "Faible")

# S4-1 -> espace, S4-2 -> rythme, S4-3 -> equipe, S4-4 -> manager,
# S4-5 -> irritant, S4-6 -> vendredi. Position in the session, not a tag.
S4_SLOTS = ("espace", "rythme", "equipe", "manager", "irritant", "vendredi")

# ── The ten S0 bipolar axes ──────────────────────────────────────────────────
# label / neg / pos are the counselor manual's wording and appear only on the
# counselor's synthesis sheet. plain_neg / plain_pos / tension are plain French
# with no framework word in them, and are the only form that reaches a prompt or
# the _voyage block — see scoring.prompt_context(), which is pure over these.
AXES: dict[str, dict[str, str]] = {
    "A1": {
        "label": "Mobilité territoriale",
        "neg": "Ancrage local",
        "pos": "Mobilité / international",
        "plain_neg": "rester près de chez elle",
        "plain_pos": "bouger, voir d'autres pays",
        "tension": "ancrage vs mobilité",
    },
    "A2": {
        "label": "Visibilité",
        "neg": "Discrétion",
        "pos": "Reconnaissance publique",
        "plain_neg": "travailler dans l'ombre",
        "plain_pos": "être reconnue publiquement",
        "tension": "discrétion vs reconnaissance",
    },
    "A3": {
        "label": "Rapport au collectif",
        "neg": "Indépendance / solo",
        "pos": "Collectif / équipe",
        "plain_neg": "travailler seule",
        "plain_pos": "travailler en équipe",
        "tension": "solo vs collectif",
    },
    "A4": {
        "label": "Échelle d'impact",
        "neg": "Impact local",
        "pos": "Impact global / systémique",
        "plain_neg": "compter pour les gens autour d'elle",
        "plain_pos": "un impact visible",
        "tension": "impact local vs impact global",
    },
    "A5": {
        "label": "Sécurité vs risque",
        "neg": "Stabilité / salariat",
        "pos": "Risque / entrepreneuriat",
        "plain_neg": "un cadre stable",
        "plain_pos": "prendre des risques",
        "tension": "sécurité vs risque",
    },
    "A6": {
        "label": "Type de création",
        "neg": "Organisation / méthode",
        "pos": "Expression libre",
        "plain_neg": "organiser et planifier",
        "plain_pos": "créer librement",
        "tension": "méthode vs expression libre",
    },
    "A7": {
        "label": "Nature du lien",
        "neg": "Systèmes / idées",
        "pos": "Lien humain direct",
        "plain_neg": "les systèmes et les idées",
        "plain_pos": "le lien avec les gens",
        "tension": "idées vs personnes",
    },
    "A8": {
        "label": "Temporalité de l'impact",
        "neg": "Long terme / différé",
        "pos": "Impact immédiat / visible",
        "plain_neg": "construire sur la durée",
        "plain_pos": "voir le résultat tout de suite",
        "tension": "impact différé vs impact immédiat",
    },
    "A9": {
        "label": "Rapport au corps",
        "neg": "Sédentaire / bureau",
        "pos": "Terrain / action physique",
        "plain_neg": "le bureau et la réflexion",
        "plain_pos": "le terrain et l'action",
        "tension": "bureau vs terrain",
    },
    "A10": {
        "label": "Transmission vs expertise",
        "neg": "Expertise individuelle",
        "pos": "Transmission / enseigner",
        "plain_neg": "maîtriser un domaine",
        "plain_pos": "transmettre",
        "tension": "expertise vs transmission",
    },
}


def axis(axis_id: str) -> dict:
    """One axis. Raises KeyError on an unknown id — a caller asking for an axis
    that doesn't exist has a bug, and returning None would hide it."""
    return AXES[axis_id]

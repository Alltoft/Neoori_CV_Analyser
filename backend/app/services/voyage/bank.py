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


# ── The six sessions ─────────────────────────────────────────────────────────
# Text is verbatim from neoori_cahier_papier.pdf. Tags are from the counselor
# manual. Session order is the play order; item order within a session is the
# order they appear on paper.

_SESSION_0 = {
    "n": "0",
    "title": "Dans 10 ans",
    "subtitle": "Ta vision instinctive — 20 affirmations",
    "intro": [
        "Dans 10 ans, tout s'est passé comme tu l'espérais. Tu travailles. "
        "Pas parce que tu le dois — mais parce que tu le veux. "
        "À quoi ressemble ta vie ?",
        "Pour chaque affirmation : coche ✓ si ça te parle, ✗ si ce n'est pas toi.",
        "Fais confiance à ton premier ressenti. Pas de réflexion — instinctif.",
    ],
    "outro": [],
    "duration": "5 min",
    "kind": KIND_CHECKLIST,
    "items": [
        {"id": "S0-01", "text": "Travailler dehors, sur le terrain, en mouvement",
         "axes": [("A9", 1)]},
        {"id": "S0-02", "text": "Avoir mes propres horaires, travailler à mon rythme",
         "axes": [("A2", 1), ("A5", 1)]},
        {"id": "S0-03", "text": "Aider des personnes au quotidien",
         "axes": [("A7", 1)]},
        {"id": "S0-04", "text": "Diriger une équipe ou une entreprise",
         "axes": [("A2", 1), ("A4", 1)]},
        {"id": "S0-05", "text": "Créer des choses avec mes mains (objets, bâtiments...)",
         "axes": [("A6", 1), ("A9", 1)]},
        {"id": "S0-06", "text": "Analyser, comprendre, résoudre des problèmes complexes",
         "axes": [("A6", 1), ("A8", 1)]},
        {"id": "S0-07", "text": "Créer des contenus, des images, de la musique, du texte",
         "axes": [("A6", 1)]},
        {"id": "S0-08", "text": "Voyager, travailler dans plusieurs pays ou villes",
         "axes": [("A1", 1)]},
        {"id": "S0-09", "text": "Enseigner, transmettre, former",
         "axes": [("A7", 1), ("A10", 1)]},
        {"id": "S0-10", "text": "Innover, créer un projet qui n'existe pas encore",
         "axes": [("A5", 1), ("A6", 1)]},
        {"id": "S0-11", "text": "Avoir un emploi stable avec un salaire régulier",
         "axes": [("A5", -1)]},
        {"id": "S0-12", "text": "Être connu(e), avoir une visibilité publique",
         "axes": [("A2", 1), ("A4", 1)]},
        {"id": "S0-13", "text": "Travailler seul(e) sur des projets indépendants",
         "axes": [("A3", -1)]},
        {"id": "S0-14", "text": "Travailler en grande équipe, beaucoup d'interactions",
         "axes": [("A3", 1)]},
        {"id": "S0-15", "text": "Avoir un impact visible sur la société ou le monde",
         "axes": [("A4", 1)]},
        {"id": "S0-16", "text": "Maîtriser un domaine technique pointu",
         "axes": [("A8", 1), ("A10", 1)]},
        {"id": "S0-17", "text": "Organiser, planifier, gérer des projets",
         "axes": [("A6", -1)]},
        {"id": "S0-18", "text": "Travailler dans le secteur du soin ou du social",
         "axes": [("A7", 1)]},
        {"id": "S0-19", "text": "Gagner beaucoup d'argent",
         "axes": [("A5", 1)]},
        {"id": "S0-20", "text": "Être utile à ma communauté locale",
         "axes": [("A4", -1), ("A7", 1)]},
    ],
    "billet": [
        {"key": "top3", "label": "Les 3 affirmations qui m'ont le plus parlé :"},
        {"key": "surprise", "label": "Quelque chose qui m'a surpris(e) dans mes réponses :"},
    ],
}


SESSIONS: list[dict] = [_SESSION_0]


def axis_items(axis_id: str) -> list[tuple[str, int]]:
    """Every S0 item loading on this axis, as (item_id, sign) in item order."""
    out = []
    for item in _SESSION_0["items"]:
        for loaded_axis, sign in item["axes"]:
            if loaded_axis == axis_id:
                out.append((item["id"], sign))
    return out

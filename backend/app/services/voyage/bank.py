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


_SESSION_1 = {
    "n": "1",
    "title": "Ce que tu faisais naturellement",
    "subtitle": "Là où tout a commencé… · 6 scènes de ton enfance",
    "intro": [
        "Bienvenue dans cette session.",
        "Aujourd'hui, on remonte plus loin. Bien plus loin. "
        "On retourne dans ta cour d'école. "
        "L'époque où quelque chose, déjà, te branchait. "
        "Où tu étais naturellement, sans réfléchir.",
        "Je vais te décrire 6 scènes de vie. Pour chacune, une question simple : "
        "quelle était TA place là-dedans ?",
    ],
    "outro": [
        "Voilà. Tu viens de poser les 6 premières pierres de ton portrait Neoori.",
        "Ce que tu as choisi, ce ne sont pas des réponses à un questionnaire. "
        "Ce sont des empreintes. Des traces laissées par ton fonctionnement naturel.",
    ],
    "duration": "15–20 min",
    "kind": KIND_SCENES,
    "items": [
        {
            "id": "S1-1",
            "title": "La cabane",
            "subtitle": "Ce que tu construisais avec les autres",
            "narrative": [
                "Il y a des bouts de bois, des cartons, des couvertures usées.",
                "Et une idée qui flotte dans l'air : construire une cabane.",
                "Autour de cette cabane, il y a toujours plusieurs tribus d'enfants.",
                "Toi, tu repères instinctivement OÙ TU ÉTAIS.",
            ],
            "question": "À cet âge-là… tu te reconnaissais dans quel groupe ?",
            "options": [
                {"letter": "A", "label": "Les architectes",
                 "text": "Ceux qui dessinaient le plan, qui avaient la vision.",
                 "plain": "tu dessinais le plan, tu avais la vision",
                 "riasec": {"R": 1, "I": 1, "E": 1, "C": 1}},
                {"letter": "B", "label": "Les bâtisseurs",
                 "text": "Ceux qui attrapaient les planches et construisaient. L'énergie brute.",
                 "plain": "tu attrapais les planches et tu construisais",
                 "riasec": {"R": 2, "C": 1}},
                {"letter": "C", "label": "Les prospecteurs",
                 "text": "Ceux qui partaient fouiller les garages, qui ramenaient LE bon carton.",
                 "plain": "tu partais chercher et tu ramenais ce qu'il fallait",
                 "riasec": {"R": 1, "I": 1}},
                {"letter": "D", "label": "Les décorateurs",
                 "text": "Ceux qui rendaient l'intérieur vivable et chaleureux.",
                 "plain": "tu rendais l'endroit vivable et chaleureux",
                 "riasec": {"A": 2, "C": 1}},
                {"letter": "E", "label": "Les gardiens",
                 "text": "Ceux qui montaient la garde, négociaient le territoire.",
                 "plain": "tu gardais et tu négociais le territoire",
                 "riasec": {"S": 1, "E": 1}},
                {"letter": "F", "label": "Les rêveurs",
                 "text": "Ceux qui racontaient des histoires une fois la cabane finie.",
                 "plain": "tu racontais les histoires une fois la cabane finie",
                 "riasec": {"A": 1, "I": 1}},
            ],
        },
        {
            "id": "S1-2",
            "title": "Le cours qu'on attendait",
            "subtitle": "La matière où le temps disparaissait",
            "narrative": [
                "La plupart des cours… bon. Mais il y avait CE cours,",
                "où le temps n'existait plus. Où la sonnerie te faisait sursauter.",
            ],
            "question": "L'ambiance qui te parle le plus viscéralement :",
            "options": [
                {"letter": "A", "label": "Le labo",
                 "text": "Microscopes, réactions chimiques. Le plaisir de comprendre les rouages.",
                 "plain": "le plaisir de comprendre comment les choses marchent",
                 "riasec": {"I": 2, "C": 1}},
                {"letter": "B", "label": "L'atelier",
                 "text": "Travaux manuels. La fierté de voir quelque chose naître entre ses mains.",
                 "plain": "la fierté de voir quelque chose naître entre tes mains",
                 "riasec": {"R": 2, "C": 1}},
                {"letter": "C", "label": "La scène",
                 "text": "Théâtre, musique, exposé. Le trac qui devient excitation.",
                 "plain": "le trac qui devient de l'excitation devant les autres",
                 "riasec": {"A": 2, "S": 1, "E": 1}},
                {"letter": "D", "label": "Le terrain",
                 "text": "Sport, sorties nature. S'adapter au réel, coordonner son corps.",
                 "plain": "t'adapter au réel, bouger, coordonner ton corps",
                 "riasec": {"R": 1, "S": 1}},
                {"letter": "E", "label": "La bibliothèque",
                 "text": "Le plaisir des mots, des histoires, des univers inventés.",
                 "plain": "le plaisir des mots et des univers inventés",
                 "riasec": {"I": 1, "A": 2}},
                {"letter": "F", "label": "La cour",
                 "text": "L'intercours. Organiser le jeu, convaincre les copains, rassembler.",
                 "plain": "organiser le jeu, convaincre, rassembler",
                 "riasec": {"E": 2, "S": 1}},
            ],
        },
        {
            "id": "S1-3",
            "title": "L'histoire qu'on racontait",
            "subtitle": "Les archétypes de l'enfance",
            "narrative": [
                "Quand t'étais petit(e), les adultes déposaient en toi des graines de métiers.",
                "Lequel de ces archétypes résonne encore — celui qui, à 8 ans, "
                "t'a fait dire « plus tard, je veux faire ça » pendant une semaine ?",
            ],
            "question": "Ta pulsion derrière, elle était réelle. La tienne, c'était quoi ?",
            "options": [
                {"letter": "A", "label": "L'archéologue",
                 "text": "Celui qui découvre des trucs enfouis, qui lit le passé comme un livre.",
                 "plain": "découvrir ce qui est enfoui et le déchiffrer",
                 "riasec": {"I": 2, "R": 1}},
                {"letter": "B", "label": "L'astronaute",
                 "text": "Celui qui va là où personne n'est allé. La conquête.",
                 "plain": "aller là où personne n'est allé",
                 "riasec": {"I": 1, "E": 2}},
                {"letter": "C", "label": "Le vétérinaire",
                 "text": "Celui qui soigne, qui répare le vivant. La douceur, le soin.",
                 "plain": "soigner, réparer le vivant",
                 "riasec": {"S": 2, "R": 1}},
                {"letter": "D", "label": "Le pompier",
                 "text": "Celui qui sauve. Le courage physique, l'action héroïque, l'urgence.",
                 "plain": "sauver, agir dans l'urgence",
                 "riasec": {"R": 2, "S": 1}},
                {"letter": "E", "label": "La maîtresse/le maître",
                 "text": "Celui qui apprend aux autres. La transmission.",
                 "plain": "apprendre aux autres, transmettre",
                 "riasec": {"S": 2, "C": 1}},
                {"letter": "F", "label": "Le/la chef(fe)",
                 "text": "Celui qui décide. Le pouvoir, la responsabilité.",
                 "plain": "décider et porter la responsabilité",
                 "riasec": {"E": 2, "C": 1}},
            ],
        },
        {
            "id": "S1-4",
            "title": "Le jeu dont tu ne te lassais pas",
            "subtitle": "L'activité qui faisait perdre le temps",
            "narrative": [
                "On a tous eu CE jeu. Une activité ludique qui pouvait nous occuper des heures.",
                "Laquelle te faisait vraiment perdre la notion du temps ?",
            ],
            "question": "Laquelle te faisait vraiment kiffer ?",
            "options": [
                {"letter": "A", "label": "Construire",
                 "text": "Légos, Kapla, cabanes dans le jardin. La création matérielle.",
                 "plain": "construire des choses de tes mains",
                 "riasec": {"R": 2, "C": 1}},
                {"letter": "B", "label": "Stratégie",
                 "text": "Échecs, Risk. Le jeu où on gagnait par le plan, la ruse, l'intelligence.",
                 "plain": "gagner par le plan et la ruse",
                 "riasec": {"I": 2, "E": 1}},
                {"letter": "C", "label": "Imaginer",
                 "text": "Playmobil, poupées, les univers qu'on inventait. Fiction, faire-semblant.",
                 "plain": "inventer des univers",
                 "riasec": {"A": 2, "I": 1}},
                {"letter": "D", "label": "Conquérir",
                 "text": "Jeu vidéo d'action, cache-cache, sport. Adrénaline, défi physique.",
                 "plain": "l'adrénaline et le défi physique",
                 "riasec": {"R": 1, "E": 2}},
                {"letter": "E", "label": "Collectionner",
                 "text": "Cartes, timbres, billes. L'ordre, le classement, la complétude.",
                 "plain": "l'ordre, le classement, la collection complète",
                 "riasec": {"C": 2}},
                {"letter": "F", "label": "Partager",
                 "text": "Jeux de société, être ensemble. La connivence, le lien, le collectif.",
                 "plain": "être ensemble, la connivence",
                 "riasec": {"S": 2}},
            ],
        },
        {
            "id": "S1-5",
            "title": "Le moment de fierté",
            "subtitle": "La fierté qui montait de l'intérieur",
            "narrative": [
                "Un moment, entre 6 et 12 ans, où tu as ressenti une fierté immense.",
                "Pas celle que les adultes t'ont donnée — celle qui est montée de l'intérieur.",
            ],
            "question": "En fermant les yeux… lequel de ces souvenirs émet encore une petite lumière ?",
            "options": [
                {"letter": "A", "label": "De ses mains",
                 "text": "J'ai réussi à faire quelque chose de mes mains. "
                         "Un objet qui n'existait pas avant.",
                 "plain": "faire de tes mains un objet qui n'existait pas",
                 "riasec": {"R": 2, "C": 1}},
                {"letter": "B", "label": "Comprendre",
                 "text": "J'ai compris quelque chose de compliqué. "
                         "« Ahhh, c'est ça ! » La lumière, l'intuition.",
                 "plain": "comprendre enfin quelque chose de compliqué",
                 "riasec": {"I": 2}},
                {"letter": "C", "label": "Captiver",
                 "text": "J'ai fait rire ou j'ai captivé. J'ai raconté, et les autres ont réagi.",
                 "plain": "captiver, raconter et voir les autres réagir",
                 "riasec": {"A": 2, "S": 1}},
                {"letter": "D", "label": "Gagner",
                 "text": "J'ai gagné. Le match, la compétition, la course. "
                         "Le sentiment de la victoire.",
                 "plain": "gagner, le sentiment de la victoire",
                 "riasec": {"E": 2, "R": 1}},
                {"letter": "E", "label": "Aider",
                 "text": "J'ai aidé. J'ai consolé quelqu'un, défendu un plus petit.",
                 "plain": "aider, consoler, défendre plus petit que toi",
                 "riasec": {"S": 2}},
                {"letter": "F", "label": "Organiser",
                 "text": "J'ai organisé. J'ai réuni, mené le projet, décidé. Et ça a marché.",
                 "plain": "organiser, réunir, mener le projet",
                 "riasec": {"E": 1, "C": 2}},
            ],
        },
        {
            "id": "S1-6",
            "title": "Ce qu'on disait de toi",
            "subtitle": "Le regard des autres — enfant",
            "narrative": [
                "Quand tu étais enfant, les adultes utilisaient des mots pour te décrire.",
                "Des qualificatifs qui revenaient. Lequel collait le plus à ta peau d'enfant ?",
            ],
            "question": "S'il y avait UN adjectif qui revenait comme un leitmotiv… c'était lequel ?",
            "options": [
                {"letter": "A", "label": "Curieux(se)",
                 "text": "« Il/elle est curieux(se) » — Tu posais tout le temps des questions.",
                 "plain": "on te disait curieux, tu posais tout le temps des questions",
                 "riasec": {"I": 2}},
                {"letter": "B", "label": "Habile de ses mains",
                 "text": "« Il/elle est habile de ses mains » — Tu réparais, bricolais, construisais.",
                 "plain": "on te disait habile de tes mains",
                 "riasec": {"R": 2}},
                {"letter": "C", "label": "Imaginatif(ve)",
                 "text": "« Il/elle est imaginatif(ve) » — Tu inventais des histoires, des mondes.",
                 "plain": "on te disait imaginatif, tu inventais des mondes",
                 "riasec": {"A": 2}},
                {"letter": "D", "label": "Sportif(ve)",
                 "text": "« Il/elle est sportif(ve) » — Tu avais besoin de bouger, courir.",
                 "plain": "on te disait sportif, tu avais besoin de bouger",
                 "riasec": {"R": 2, "E": 1}},
                {"letter": "E", "label": "Sensible",
                 "text": "« Il/elle est sensible » — Tu ressentais les émotions des autres.",
                 "plain": "on te disait sensible aux émotions des autres",
                 "riasec": {"S": 2}},
                {"letter": "F", "label": "Suite dans les idées",
                 "text": "« Il/elle a de la suite dans les idées » — Tu ne lâchais pas, tu insistais.",
                 "plain": "on disait que tu avais de la suite dans les idées",
                 "riasec": {"E": 1, "C": 2}},
                {"letter": "G", "label": "Fédérateur(trice)",
                 "text": "« Il/elle est fédérateur(trice) » — Les jeux s'organisaient autour de toi.",
                 "plain": "les jeux s'organisaient autour de toi",
                 "riasec": {"S": 1, "E": 2}},
                {"letter": "H", "label": "Sérieux(se)",
                 "text": "« Il/elle est sérieux(se) » — Tu écoutais, tu suivais les règles.",
                 "plain": "on te disait sérieux, tu suivais les règles",
                 "riasec": {"C": 2}},
            ],
        },
    ],
    "billet": [
        {"key": "cabane", "label": "Dans la cabane, tu étais plutôt :"},
        {"key": "jeu", "label": "Au jeu, tu préférais :"},
        {"key": "fierte", "label": "Ta fierté venait de :"},
        {"key": "regard", "label": "Les autres disaient que tu étais :"},
    ],
}


SESSIONS: list[dict] = [_SESSION_0, _SESSION_1]


def riasec_maxima() -> dict[str, int]:
    """The best score reachable per RIASEC letter, computed from session 1.

    Computed, never a literal: the counselor manual prints E 10 and C 10, but
    summing the best available option per scene gives E 11 and C 9. Those two
    are transcription slips in the paper sheet (spec errata 17b), and a
    normalisation against the printed maxima would score E too high and C too
    low for every person, invisibly.
    """
    maxima = {letter: 0 for letter in RIASEC_LETTERS}
    for scene in _SESSION_1["items"]:
        for letter in RIASEC_LETTERS:
            best = max(
                (option.get("riasec", {}).get(letter, 0) for option in scene["options"]),
                default=0,
            )
            maxima[letter] += best
    return maxima


def axis_items(axis_id: str) -> list[tuple[str, int]]:
    """Every S0 item loading on this axis, as (item_id, sign) in item order."""
    out = []
    for item in _SESSION_0["items"]:
        for loaded_axis, sign in item["axes"]:
            if loaded_axis == axis_id:
                out.append((item["id"], sign))
    return out

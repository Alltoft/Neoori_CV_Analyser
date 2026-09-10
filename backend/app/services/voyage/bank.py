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


_SESSION_2 = {
    "n": "2",
    "title": "Ce qui compte vraiment pour toi",
    "subtitle": "Ce qui te donne envie de te lever le matin · 7 situations",
    "intro": [
        "Aujourd'hui, on va plus loin. On va chercher ce qui te fait vraiment vibrer.",
        "Pas ce qui est « bien » ou « raisonnable ». Ce qui, quand c'est là, "
        "te donne envie de te lever le matin. Et quand c'est absent, te vide de "
        "l'intérieur, même si tout va bien.",
        "7 scènes. Dans chacune, entoure la lettre qui te correspond.",
    ],
    "outro": [],
    "duration": "20 min",
    "kind": KIND_SCENES,
    "items": [
        {
            "id": "S2-1",
            "title": "Le projet passion",
            "subtitle": "La liberté d'un projet sans contrainte",
            "narrative": [
                "On t'a confié un projet. Carte blanche sur la façon de le mener.",
                "Personne ne regarde par-dessus ton épaule. Résultat dans 3 mois.",
            ],
            "question": "Comment tu fonctionnes, toi ? Avant la raison, avant la stratégie.",
            "options": [
                {"letter": "A", "label": "Structure dès le début",
                 "text": "Tu structures tout dès le premier jour. Planning, jalons, deadlines. "
                         "Tu sais où tu vas.",
                 "plain": "tu structures tout dès le premier jour",
                 # manual: "SDT : Sécurité cognitive" — not one of the three SDT
                 # needs, so only the Schwartz value it also names is carried.
                 "schwartz": ["conformite"],
                 "big5": {"conscienciosite": 1}},
                {"letter": "B", "label": "Explorer d'abord",
                 "text": "Tu commences par explorer. Tu testes, tu tâtonnes, "
                         "tu vois ce qui émerge.",
                 "plain": "tu explores et tu tâtonnes avant de décider",
                 "sdt": "autonomie", "schwartz": ["autodirection"]},
                {"letter": "C", "label": "Aller vers les autres",
                 "text": "Tu vas parler aux gens. Tu échanges, tu construis avec eux. "
                         "Le collectif te porte.",
                 "plain": "tu vas parler aux gens, le collectif te porte",
                 "sdt": "appartenance", "schwartz": ["bienveillance"]},
                {"letter": "D", "label": "Fond et qualité",
                 "text": "Tu te concentres sur le fond. Tu veux que ce soit parfait, "
                         "que ça tienne la route.",
                 "plain": "tu veux que ça tienne vraiment la route",
                 "sdt": "competence", "schwartz": ["reussite"]},
            ],
        },
        {
            "id": "S2-2",
            "title": "La proposition qu'on t'a faite",
            "subtitle": "Quitter la sécurité pour l'aventure",
            "narrative": [
                "Tu es bien là où tu es. L'équipe sympa, rien à redire.",
                "Et là, on te propose autre chose. Différent, un peu risqué — "
                "mais si ça marche, ça peut être grand.",
            ],
            "question": "Écoute ton premier réflexe. Avant la raison. Qu'est-ce qui se passe en toi ?",
            "options": [
                {"letter": "A", "label": "Rester — sécurité",
                 "text": "Tu réfléchis, tu pèses le pour et le contre, et tu restes. "
                         "La sécurité, c'est trop important.",
                 "plain": "tu restes, la sécurité compte trop",
                 "schwartz": ["conservation", "securite"]},
                {"letter": "B", "label": "Foncer — aventure",
                 "text": "Ton cœur s'emballe. Le risque, l'aventure — c'est ça qui te fait "
                         "sentir vivant(e). Tu te lances.",
                 "plain": "tu te lances, le risque te fait te sentir vivant",
                 "schwartz": ["stimulation"], "big5": {"ouverture": 1}},
                {"letter": "C", "label": "Consulter — lien",
                 "text": "Tu demandes conseil autour de toi. Tu ne prendras pas cette "
                         "décision seul(e).",
                 "plain": "tu ne décides pas seul, tu demandes conseil",
                 "schwartz": ["bienveillance"], "sdt": "appartenance"},
                {"letter": "D", "label": "Questionner le sens",
                 "text": "Tu te demandes : « est-ce que ça a du sens ? » "
                         "Si c'est juste pour gagner plus, ça ne t'intéresse pas.",
                 "plain": "tu demandes d'abord si ça a du sens",
                 "schwartz": ["universalisme"]},
            ],
        },
        {
            "id": "S2-3",
            "title": "La reconnaissance",
            "subtitle": "Ce qui te touche vraiment après un succès",
            "narrative": [
                "Tu viens de finir un gros projet. Ça a marché. Vraiment bien marché.",
                "Le lendemain, plusieurs choses se passent. "
                "Laquelle te touche le PLUS profondément ?",
            ],
            "question": "Laquelle fait vibrer quelque chose en toi, là, maintenant ?",
            "options": [
                {"letter": "A", "label": "Validation du chef",
                 "text": "Ton responsable te prend à part : « Franchement, super boulot. "
                         "J'ai vu tout ce que t'as mis là-dedans. »",
                 "plain": "que ton responsable voie ce que tu y as mis",
                 # manual: "Besoin de feedback hiérarchique" — nearest closed value.
                 "schwartz": ["reussite"]},
                {"letter": "B", "label": "Verre en équipe",
                 "text": "Ton équipe t'emmène boire un verre. Personne ne fait de discours, "
                         "mais tout le monde est là.",
                 "plain": "que toute l'équipe soit là, sans discours",
                 "sdt": "appartenance", "schwartz": ["bienveillance"]},
                {"letter": "C", "label": "Reconnaissance publique",
                 "text": "On annonce les résultats en réunion. Ton nom est cité devant tout le monde.",
                 "plain": "que ton nom soit cité devant tout le monde",
                 "schwartz": ["reussite", "pouvoir"]},
                {"letter": "D", "label": "Satisfaction intérieure",
                 "text": "Personne ne dit rien. Mais toi, tu sais que t'as fait du bon boulot. "
                         "La satisfaction intérieure te suffit.",
                 "plain": "savoir toi-même que c'était du bon travail te suffit",
                 "sdt": "competence", "schwartz": ["autodirection"]},
            ],
        },
        {
            "id": "S2-4",
            "title": "Le conflit d'équipe",
            "subtitle": "Valeurs en tension",
            "narrative": [
                "Dans ton équipe, il y a des tensions. Deux personnes ne sont pas d'accord.",
                "L'un veut livrer vite. L'autre veut prendre le temps, faire solide. "
                "Toi, tu te situes où ?",
            ],
            "question": "Instinctivement, tu fais quoi dans ce genre de situation ?",
            "options": [
                {"letter": "A", "label": "Compromis",
                 "text": "Tu écoutes les deux, tu proposes une synthèse, tu cherches le compromis. "
                         "L'harmonie du groupe est primordiale.",
                 "plain": "tu cherches le compromis, l'harmonie du groupe compte",
                 "big5": {"agreabilite": 1}, "schwartz": ["bienveillance"]},
                {"letter": "B", "label": "Prendre position",
                 "text": "Tu prends position. Clairement. Tu dis ce que tu penses, "
                         "même si ça crée un clash.",
                 "plain": "tu dis ce que tu penses même si ça crée un clash",
                 "big5": {"agreabilite": -1}, "schwartz": ["integrite"]},
                {"letter": "C", "label": "Analyser le fond",
                 "text": "Tu essaies de comprendre le fond du problème. "
                         "Tu joues le médiateur analytique.",
                 "plain": "tu cherches le fond du problème avant de trancher",
                 "big5": {"ouverture": 1}},
                {"letter": "D", "label": "Procédure collective",
                 "text": "Tu proposes qu'on vote en réunion, qu'on décide collectivement "
                         "et qu'on avance. La procédure rassure.",
                 "plain": "tu proposes qu'on décide collectivement et qu'on avance",
                 "schwartz": ["conformite"]},
            ],
        },
        {
            "id": "S2-5",
            "title": "Le moment difficile",
            "subtitle": "Pourquoi on tient quand c'est dur",
            "narrative": [
                "Ça fait plusieurs mois que ça ne va pas. Le travail est devenu difficile.",
                "Pas intéressant. Parfois même un peu absurde. "
                "Mais il y a une raison pour laquelle tu restes.",
            ],
            "question": "La raison profonde. Celle qui est honnête. Laquelle te ressemble ?",
            "options": [
                {"letter": "A", "label": "Les autres comptent",
                 "text": "Tu as des gens qui comptent sur toi. Tu ne peux pas les laisser tomber.",
                 "plain": "des gens comptent sur toi et tu ne les lâches pas",
                 "schwartz": ["bienveillance"]},
                {"letter": "B", "label": "Je me suis engagé(e)",
                 "text": "Tu t'es engagé(e). Tu as promis que tu finirais. "
                         "Tu n'es pas du genre à lâcher.",
                 "plain": "tu as promis de finir et tu finis",
                 "schwartz": ["conformite", "integrite"]},
                {"letter": "C", "label": "Ça a de l'impact",
                 "text": "Tu sais que ce que tu fais a un impact. Quelque part, ça aide des gens.",
                 "plain": "ce que tu fais aide des gens quelque part",
                 "schwartz": ["universalisme"]},
                {"letter": "D", "label": "Je dois prouver",
                 "text": "Tu veux prouver que tu peux le faire. À toi-même, d'abord. "
                         "Abandonner = reconnaître l'échec.",
                 "plain": "tu veux te prouver à toi-même que tu peux le faire",
                 "schwartz": ["reussite"]},
            ],
        },
        {
            "id": "S2-6",
            "title": "Le chef idéal",
            "subtitle": "Besoins relationnels au travail",
            "narrative": [
                "Si tu devais décrire le chef idéal pour toi,",
                "celui avec qui tu donnerais le meilleur de toi-même, ce serait lequel ?",
            ],
            "question": "Le chef avec lequel tu t'épanouirais vraiment. Sans compromis. C'est lequel ?",
            "options": [
                {"letter": "A", "label": "Confiance + autonomie",
                 "text": "Celui qui te fait confiance, qui te laisse de l'autonomie. "
                         "« Débrouille-toi, je te fais confiance. »",
                 "plain": "celui qui te laisse de l'autonomie",
                 "sdt": "autonomie", "schwartz": ["autodirection"]},
                {"letter": "B", "label": "Exigence + défi",
                 "text": "Celui qui est exigeant. Qui te pousse à te dépasser, "
                         "qui attend le meilleur de toi.",
                 "plain": "celui qui est exigeant et te pousse à te dépasser",
                 "schwartz": ["hedonisme", "reussite"]},
                {"letter": "C", "label": "Lien + présence",
                 "text": "Celui qui est présent. Qui prend des nouvelles, "
                         "crée une vraie relation humaine.",
                 "plain": "celui qui est présent et prend des nouvelles",
                 "sdt": "appartenance"},
                {"letter": "D", "label": "Vision + sécurité",
                 "text": "Celui qui sait où il va. Vision claire, décisions difficiles. "
                         "« On va par là, suis-moi. »",
                 "plain": "celui qui sait où il va et l'annonce clairement",
                 "schwartz": ["securite", "pouvoir"]},
            ],
        },
        {
            "id": "S2-7",
            "title": "Dans 20 ans",
            "subtitle": "La projection existentielle",
            "narrative": [
                "Ultime scène pour aujourd'hui. On se projette loin. Très loin. Dans 20 ans.",
                "Quand tu regardes ta vie professionnelle en arrière, qu'est-ce qui te fera "
                "dire : « voilà, ça valait le coup, je ne regrette rien » ?",
            ],
            "question": "Sans filtre. La réponse qui vient du ventre. Dans 20 ans, qu'est-ce qui compte ?",
            "options": [
                {"letter": "A", "label": "Construire / Héritage",
                 "text": "« J'ai construit des choses qui durent. Des réalisations dont je suis "
                         "fier(e), quelque chose qui restera. »",
                 "plain": "tu veux avoir construit des choses qui durent",
                 "schwartz": ["reussite"]},
                {"letter": "B", "label": "Aventure / Intensité",
                 "text": "« J'ai vécu des aventures incroyables. Des projets fous, "
                         "des moments où mon cœur battait fort. »",
                 "plain": "tu veux avoir vécu des projets fous",
                 "schwartz": ["hedonisme", "stimulation"]},
                {"letter": "C", "label": "Utilité / Sens",
                 "text": "« J'ai été utile. J'ai aidé des gens, j'ai changé des vies. "
                         "Le monde est un peu meilleur grâce à moi. »",
                 "plain": "tu veux avoir été utile et avoir changé des vies",
                 "schwartz": ["universalisme"]},
                {"letter": "D", "label": "Liens / Collectif",
                 "text": "« J'étais entouré(e). Des équipes formidables, des liens forts. "
                         "Je n'étais pas seul(e). »",
                 "plain": "tu veux avoir été entouré de liens forts",
                 "schwartz": ["bienveillance"], "sdt": "appartenance"},
                {"letter": "E", "label": "Compétence / Maîtrise",
                 "text": "« J'ai grandi. Je suis devenu(e) meilleur(e), plus compétent(e), "
                         "plus sage. »",
                 "plain": "tu veux être devenu meilleur et plus sage",
                 "sdt": "competence"},
                {"letter": "F", "label": "Liberté / Indépendance",
                 "text": "« J'étais libre. J'ai fait ce que je voulais, quand je voulais. "
                         "Ma vie m'appartenait. »",
                 "plain": "tu veux que ta vie t'appartienne",
                 "schwartz": ["autodirection"], "sdt": "autonomie"},
            ],
        },
    ],
    "billet": [
        {"key": "vibrer", "label": "Ce qui me fait vibrer, c'est quand :"},
        {"key": "vide", "label": "Ce qui me vide, c'est quand :"},
        {"key": "vingt_ans", "label": "Dans 20 ans, je veux pouvoir dire que :"},
    ],
}


_SESSION_3 = {
    "n": "3",
    "title": "Comment tu penses et tu fonctionnes",
    "subtitle": "Pas ce que tu fais — comment tu le fais · 7 situations",
    "intro": [
        "Les fois précédentes, on a regardé ce que tu faisais naturellement, "
        "et ce qui te fait vibrer.",
        "Aujourd'hui, on s'intéresse à quelque chose de plus difficile à voir. "
        "Pas ce que tu fais. Comment tu le fais.",
        "Ta façon naturelle de traiter l'information. De prendre des décisions. "
        "D'interagir avec les autres. De te recharger, de te fatiguer.",
    ],
    "outro": [],
    "duration": "20 min",
    "kind": KIND_SCENES,
    "items": [
        {
            "id": "S3-1",
            "title": "La réunion surprise",
            "subtitle": "Décider sans préparation",
            "narrative": [
                "Il est 9h. On t'annonce une réunion dans 5 minutes.",
                "Tu n'as rien préparé. Tu dois prendre position sur un sujet important.",
            ],
            "question": "Comment tu réagis ?",
            "options": [
                {"letter": "A", "label": "S'adapte, improvise",
                 "text": "Tu t'adaptes. Tu improvises, tu te lances. L'imprévu te réveille.",
                 "plain": "tu improvises, l'imprévu te réveille",
                 "big5": {"extraversion": 1, "ouverture": 1, "nevrotisme": -1},
                 "style": "holistique"},
                {"letter": "B", "label": "Prend 5 min de structure",
                 "text": "Tu prends 5 minutes pour noter les points essentiels. "
                         "Un minimum de structure.",
                 "plain": "tu prends cinq minutes pour te donner un minimum de structure",
                 "big5": {"conscienciosite": 1}, "style": "sequentiel"},
                {"letter": "C", "label": "Écoute les autres d'abord",
                 "text": "Tu stresses un peu, mais tu écoutes les autres d'abord "
                         "avant de te positionner.",
                 "plain": "tu écoutes les autres avant de te positionner",
                 "big5": {"agreabilite": 1, "extraversion": -1}, "style": "consultatif"},
                {"letter": "D", "label": "Mal à l'aise sans prépa",
                 "text": "Tu es mal à l'aise. Décider sans préparation, c'est contre ta nature.",
                 "plain": "décider sans préparation va contre ta nature",
                 "big5": {"nevrotisme": 1, "conscienciosite": 1}},
            ],
        },
        {
            "id": "S3-2",
            "title": "Le collègue très différent",
            "subtitle": "Travailler avec son opposé",
            "narrative": [
                "Tu dois travailler pendant 3 semaines avec quelqu'un qui fonctionne "
                "à l'opposé de toi.",
                "Il/elle pense différemment, n'a pas les mêmes méthodes.",
            ],
            "question": "Comment tu vis les 3 premières semaines ?",
            "options": [
                {"letter": "A", "label": "Stimulant",
                 "text": "C'est stimulant. Les différences forcent à voir les choses autrement.",
                 "plain": "les différences te stimulent",
                 "big5": {"ouverture": 1}},
                {"letter": "B", "label": "Inconfortable → s'adapte",
                 "text": "Inconfortable au début, mais tu t'adaptes. "
                         "Tu cherches à comprendre sa logique.",
                 "plain": "tu t'adaptes et tu cherches à comprendre sa logique",
                 "big5": {"agreabilite": 1, "ouverture": 1}, "style": "adaptatif"},
                {"letter": "C", "label": "S'ajuste, harmonie",
                 "text": "Tu t'ajustes à lui/elle plus que tu ne l'exprimes. L'harmonie avant tout.",
                 "plain": "tu t'ajustes plutôt que de l'exprimer",
                 "big5": {"agreabilite": 1}},
                {"letter": "D", "label": "Épuisant",
                 "text": "C'est épuisant. Être en décalage constant, ça consomme de l'énergie.",
                 "plain": "le décalage constant te consomme de l'énergie",
                 "big5": {"nevrotisme": 1, "extraversion": -1}},
            ],
        },
        {
            "id": "S3-3",
            "title": "L'information incomplète",
            "subtitle": "Agir sans tout savoir",
            "narrative": [
                "Tu dois prendre une décision importante, mais tu n'as pas toutes "
                "les informations.",
                "Il te manque des données clés.",
            ],
            "question": "Comment tu procèdes ?",
            "options": [
                {"letter": "A", "label": "Décide quand même",
                 "text": "Tu décides quand même. Avec ce que tu as, tu avances. "
                         "L'attente est pire que l'imperfection.",
                 "plain": "tu avances avec ce que tu as",
                 "big5": {"nevrotisme": -1, "extraversion": 1}, "style": "holistique"},
                {"letter": "B", "label": "Cartographie les manques",
                 "text": "Tu cartographies ce que tu sais et ce que tu ne sais pas. "
                         "Tu identifies tes angles morts.",
                 "plain": "tu cartographies ce que tu sais et ce qui te manque",
                 "big5": {"ouverture": 1, "conscienciosite": 1}, "style": "sequentiel"},
                {"letter": "C", "label": "Demande aux autres",
                 "text": "Tu demandes à d'autres personnes. "
                         "Plusieurs perspectives compensent les manques.",
                 "plain": "tu vas chercher d'autres points de vue",
                 "big5": {"agreabilite": 1, "extraversion": 1}, "style": "consultatif"},
                {"letter": "D", "label": "Attend plus d'éléments",
                 "text": "Tu attends. Tu repousses la décision jusqu'à avoir plus d'éléments.",
                 "plain": "tu attends d'avoir plus d'éléments",
                 "big5": {"conscienciosite": 1, "nevrotisme": 1}},
            ],
        },
        {
            "id": "S3-4",
            "title": "La tâche répétitive",
            "subtitle": "Le rapport à la routine",
            "narrative": [
                "Tu dois effectuer la même tâche, dans le même ordre, "
                "tous les jours pendant un mois.",
            ],
            "question": "Au bout d'une semaine, qu'est-ce qui se passe en toi ?",
            "options": [
                {"letter": "A", "label": "S'ennuie",
                 "text": "Tu t'ennuies assez vite. La répétition t'anesthésie. "
                         "Tu as besoin de changement.",
                 "plain": "la répétition t'anesthésie vite",
                 "big5": {"ouverture": 1}},
                {"letter": "B", "label": "Confort dans la routine",
                 "text": "Tu trouves une forme de confort. Maîtriser, ne pas avoir de surprise.",
                 "plain": "tu trouves du confort à maîtriser sans surprise",
                 "big5": {"conscienciosite": 1, "ouverture": -1}},
                {"letter": "C", "label": "Optimise",
                 "text": "Tu optimises. Puisque c'est répétitif, tu cherches comment "
                         "le faire mieux.",
                 "plain": "tu cherches comment le faire mieux",
                 "big5": {"ouverture": 1, "conscienciosite": 1}, "style": "adaptatif"},
                {"letter": "D", "label": "Tient si ça a du sens",
                 "text": "Ça dépend du contexte. Si ça a du sens, tu tiens. Sinon, non.",
                 "plain": "tu tiens si ça a du sens, pas autrement",
                 # S3-4 D: manual reads "Motivation intrinsèque conditionnelle — Besoin
                 # de finalité". Neither a Big Five trait nor a cognitive style; carried
                 # as the meaning signal it is. score_s2 counts session 2 only, so this
                 # never reaches the Schwartz tally.
                 "schwartz": ["universalisme"]},
            ],
        },
        {
            "id": "S3-5",
            "title": "Le feedback difficile",
            "subtitle": "Recevoir une critique sur son travail",
            "narrative": [
                "Ton responsable t'a dit que ton travail avait des lacunes.",
                "La critique est juste, mais elle fait mal.",
            ],
            "question": "Ce soir-là, qu'est-ce qui se passe ?",
            "options": [
                {"letter": "A", "label": "Digère et avance",
                 "text": "Tu digères et tu avances. Avoir tort ne te définit pas.",
                 "plain": "avoir tort ne te définit pas, tu avances",
                 "big5": {"nevrotisme": -1}},
                {"letter": "B", "label": "Cerveau ne lâche pas",
                 "text": "Tu refais mentalement tout le chemin. "
                         "Ton cerveau ne lâche pas facilement.",
                 "plain": "tu refais mentalement tout le chemin",
                 "big5": {"nevrotisme": 1}, "style": "sequentiel"},
                {"letter": "C", "label": "Besoin d'en parler",
                 "text": "Tu as besoin d'en parler à quelqu'un de confiance.",
                 "plain": "tu as besoin d'en parler à quelqu'un de confiance",
                 "big5": {"agreabilite": 1, "extraversion": 1}, "style": "consultatif"},
                {"letter": "D", "label": "Analyse le pourquoi",
                 "text": "Tu veux comprendre exactement pourquoi c'est une erreur. Tu analyses.",
                 "plain": "tu veux comprendre exactement pourquoi",
                 "big5": {"ouverture": 1, "conscienciosite": 1}, "style": "sequentiel"},
            ],
        },
        {
            "id": "S3-6",
            "title": "Solo ou ensemble ?",
            "subtitle": "Source d'énergie au travail",
            "narrative": [
                "Pour une tâche importante qui demande beaucoup de réflexion,",
            ],
            "question": "Qu'est-ce que tu choisirais instinctivement ?",
            "options": [
                {"letter": "A", "label": "Seul(e)",
                 "text": "Seul(e). La concentration profonde, c'est là que tu produis le mieux.",
                 "plain": "tu produis le mieux dans la concentration profonde, seul",
                 "big5": {"extraversion": -1}},
                {"letter": "B", "label": "Ensemble",
                 "text": "Ensemble. Les échanges génèrent des idées que tu n'aurais pas "
                         "eues seul(e).",
                 "plain": "les échanges te donnent des idées que tu n'aurais pas eues seul",
                 "big5": {"extraversion": 1}, "style": "consultatif"},
                {"letter": "C", "label": "Seul(e) puis ensemble",
                 "text": "Seul(e) pour réfléchir, ensemble pour valider. Le meilleur des deux.",
                 "plain": "seul pour réfléchir, ensemble pour valider",
                 # S3-6 C: manual reads "Ambiversion — Style hybride". Mapped to adaptatif:
                 # switching mode by task is what STYLE_PLAIN["adaptatif"] says.
                 "style": "adaptatif"},
                {"letter": "D", "label": "S'adapte",
                 "text": "Ça dépend de la tâche. Tu t'adaptes.",
                 "plain": "tu t'adaptes à la tâche",
                 "big5": {"ouverture": 1, "agreabilite": 1}, "style": "adaptatif"},
            ],
        },
        {
            "id": "S3-7",
            "title": "La surcharge",
            "subtitle": "Quand trop de choses arrivent en même temps",
            "narrative": [
                "Trois urgences arrivent en même temps. Ton téléphone sonne. "
                "Tes collègues te sollicitent.",
            ],
            "question": "Comment tu t'en sors instinctivement ?",
            "options": [
                {"letter": "A", "label": "Priorise, liste",
                 "text": "Tu priorises. Tu fais une liste, tu identifies l'urgent et l'important.",
                 "plain": "tu fais une liste et tu tries l'urgent de l'important",
                 "big5": {"conscienciosite": 1}, "style": "sequentiel"},
                {"letter": "B", "label": "S'isole",
                 "text": "Tu t'isoles. Tu coupes les notifications, tu te mets dans une bulle.",
                 "plain": "tu coupes tout et tu te mets dans une bulle",
                 "big5": {"extraversion": -1}},
                {"letter": "C", "label": "Délègue ou demande aide",
                 "text": "Tu délègues ou tu demandes de l'aide.",
                 "plain": "tu délègues ou tu demandes de l'aide",
                 "big5": {"agreabilite": 1, "extraversion": 1}, "style": "consultatif"},
                {"letter": "D", "label": "Absorbe, jongle",
                 "text": "Tu absorbes. Tu encaisses, tu gères, tu jonglles. "
                         "Les autres sont souvent surpris.",
                 "plain": "tu encaisses et tu jongles, ça surprend les autres",
                 "big5": {"nevrotisme": -1}, "style": "holistique"},
            ],
        },
    ],
    "billet": [
        {"key": "imprevu", "label": "Face à l'imprévu, je suis plutôt :"},
        {"key": "meilleur", "label": "Je produis le mieux quand je suis :"},
        {"key": "pression", "label": "Sous pression, mon premier réflexe est de :"},
    ],
}


_SESSION_4 = {
    "n": "4",
    "title": "Le cadre qui te permet de te révéler",
    "subtitle": "Pas le métier — l'environnement · 6 situations",
    "intro": [
        "On arrive à la session qui change tout.",
        "Pas le métier. Pas le secteur. Pas la fiche de poste. Le cadre.",
        "Certains s'épanouissent dans le bruit et le mouvement. "
        "D'autres ont besoin de silence et de profondeur. "
        "Ni mieux, ni moins bien. Juste différent.",
        "Et pourtant, être dans un cadre qui ne te correspond pas, "
        "c'est l'une des causes les plus silencieuses d'épuisement professionnel.",
    ],
    "outro": [],
    "duration": "15 min",
    "kind": KIND_SCENES,
    "items": [
        {
            "id": "S4-1",
            "title": "L'espace idéal",
            "subtitle": "Le bureau de tes rêves",
            "narrative": ["Si tu pouvais choisir ton espace de travail idéal,"],
            "question": "Lequel de ces espaces t'attire instinctivement ?",
            "options": [
                {"letter": "A", "label": "Bureau fermé calme",
                 "text": "Un bureau fermé, calme, à toi. Lumière naturelle. "
                         "Tu peux fermer la porte.",
                 "plain": "un bureau fermé et calme, où tu peux fermer la porte",
                 "env": "bureau fermé et calme"},
                {"letter": "B", "label": "Open space vivant",
                 "text": "Un open space vivant, au milieu des autres. "
                         "L'énergie collective te porte.",
                 "plain": "un open space vivant, l'énergie collective te porte",
                 "env": "open space vivant"},
                {"letter": "C", "label": "Espace flexible",
                 "text": "Un espace flexible — bureau le matin, café, télétravail. "
                         "La variété te stimule.",
                 "plain": "un espace flexible, la variété te stimule",
                 "env": "espace flexible"},
                {"letter": "D", "label": "En mouvement / terrain",
                 "text": "Un espace en mouvement — chantier, terrain, déplacements. "
                         "Ton bureau, c'est le monde.",
                 "plain": "en mouvement, ton bureau c'est le monde",
                 "env": "en mouvement, sur le terrain"},
            ],
        },
        {
            "id": "S4-2",
            "title": "La journée parfaite",
            "subtitle": "Le rythme idéal",
            "narrative": ["Si tu pouvais organiser ta journée exactement comme tu le veux,"],
            "question": "Lequel de ces portraits de journée te fait dire « oui, c'est ça » ?",
            "options": [
                {"letter": "A", "label": "Tôt, calme, focus",
                 "text": "Démarrer tôt, dans le calme. Deux heures de concentration. "
                         "Puis réunions, échanges. Rentrer tôt.",
                 "plain": "démarrer tôt dans le calme, puis les échanges",
                 "env": "démarrage tôt, au calme"},
                {"letter": "B", "label": "Démarrer doucement",
                 "text": "Démarrer doucement. Pas à 100% avant 10h. "
                         "Pic d'énergie en fin de matinée ou l'après-midi.",
                 "plain": "démarrer doucement, ton pic d'énergie vient plus tard",
                 "env": "démarrage progressif"},
                {"letter": "C", "label": "Cycles courts intenses",
                 "text": "Des cycles courts et intenses : 90 minutes, vraie pause, "
                         "90 minutes. Alterner les tâches.",
                 "plain": "des cycles courts et intenses avec de vraies pauses",
                 "env": "cycles courts et intenses"},
                {"letter": "D", "label": "Sans horaire fixe",
                 "text": "Sans horaire fixe — tu travailles quand ça vient. "
                         "Tu gères ton énergie, pas ton temps.",
                 "plain": "sans horaire fixe, tu gères ton énergie plutôt que ton temps",
                 "env": "sans horaire fixe"},
            ],
        },
        {
            "id": "S4-3",
            "title": "L'équipe parfaite",
            "subtitle": "Configurations relationnelles",
            "narrative": ["Dans quel type d'équipe tu te sens le mieux ?"],
            "question": "Laquelle te correspond le mieux, toi ?",
            "options": [
                {"letter": "A", "label": "Petite équipe soudée",
                 "text": "Une petite équipe soudée — 4 à 6 personnes. "
                         "Tu te connais, tu te fais confiance.",
                 "plain": "une petite équipe soudée où on se connaît",
                 "env": "petite équipe soudée"},
                {"letter": "B", "label": "Seul(e) + référents",
                 "text": "Seul(e) avec un ou deux référents. Autonomie, "
                         "mais points réguliers avec quelqu'un de solide.",
                 "plain": "autonome, avec un ou deux référents solides",
                 "env": "autonomie avec un référent"},
                {"letter": "C", "label": "Grande équipe diverse",
                 "text": "Une grande équipe diverse. Beaucoup de profils, "
                         "d'interactions, de points de vue.",
                 "plain": "une grande équipe, beaucoup de profils et d'interactions",
                 "env": "grande équipe diverse"},
                {"letter": "D", "label": "Clarté des rôles",
                 "text": "Peu importe la taille — ce qui compte, c'est la clarté des rôles. "
                         "Qui fait quoi.",
                 "plain": "peu importe la taille, ce sont les rôles clairs qui comptent",
                 "env": "des rôles clairs"},
            ],
        },
        {
            "id": "S4-4",
            "title": "Le manager qu'on n'oublie pas",
            "subtitle": "Ce qui t'a permis de te révéler",
            "narrative": [
                "Pense à un adulte (prof, animateur, parent, entraîneur...) "
                "avec qui tu as vraiment pu être toi-même et donner le meilleur.",
            ],
            "question": "Qu'est-ce qui faisait que ça marchait ?",
            "options": [
                {"letter": "A", "label": "Confiance — essai/erreur",
                 "text": "Il/elle te faisait confiance. Te laissait essayer, rater, recommencer. "
                         "Sans surveillance.",
                 "plain": "on te laissait essayer, rater et recommencer",
                 "env": "confiance et droit à l'essai"},
                {"letter": "B", "label": "Exigeant",
                 "text": "Il/elle t'exigeait. Attendait plus que tu ne te croyais capable.",
                 "plain": "on attendait de toi plus que tu ne t'en croyais capable",
                 "env": "exigence et défi"},
                {"letter": "C", "label": "Voyait la personne",
                 "text": "Il/elle te voyait. Pas juste ta production — toi. Ce que tu traversais.",
                 "plain": "on te voyait toi, pas seulement ce que tu produisais",
                 "env": "attention à la personne"},
                {"letter": "D", "label": "Vision claire / cap",
                 "text": "Il/elle savait où aller. Vision claire, décisions difficiles. "
                         "Tu pouvais faire confiance au cap.",
                 "plain": "on savait où aller et tu pouvais faire confiance au cap",
                 "env": "un cap clair"},
            ],
        },
        {
            "id": "S4-5",
            "title": "La réunion de trop",
            "subtitle": "Ce qui épuise vs ce qui recharge",
            "narrative": [
                "Parmi ces situations, laquelle te pèse le plus ?",
                "Celle qui, à la fin de la journée, te laisse vraiment vidé(e) ?",
            ],
            "question": "Laquelle te pèse le plus ?",
            "options": [
                {"letter": "A", "label": "Réunions longues/bruyantes",
                 "text": "Les réunions longues avec trop de monde, trop de bruit. "
                         "Tu ressors épuisé(e).",
                 "plain": "les réunions longues et bruyantes t'épuisent",
                 "env": "les réunions longues et bruyantes"},
                {"letter": "B", "label": "Interruptions constantes",
                 "text": "Être constamment interrompu(e). Les notifications, "
                         "les « t'as 5 minutes ? ».",
                 "plain": "être constamment interrompu",
                 "env": "les interruptions constantes"},
                {"letter": "C", "label": "Relations tendues/floues",
                 "text": "Les relations tendues ou floues. "
                         "Sentir une tension non dite dans l'équipe.",
                 "plain": "les tensions non dites dans l'équipe",
                 "env": "les tensions non dites"},
                {"letter": "D", "label": "Absence de sens",
                 "text": "L'absence de sens visible. Des tâches dont tu ne vois pas la finalité.",
                 "plain": "des tâches dont tu ne vois pas la finalité",
                 "env": "les tâches sans finalité"},
            ],
        },
        {
            "id": "S4-6",
            "title": "Le vendredi soir",
            "subtitle": "Bilan énergétique de la semaine",
            "narrative": ["C'est vendredi soir. La semaine se termine."],
            "question": "Comment tu fermes la semaine ?",
            "options": [
                {"letter": "A", "label": "Contente des cases cochées",
                 "text": "Content(e) de ce que tu as produit. Des choses abouties, terminées. "
                         "Tu peux cocher des cases.",
                 "plain": "content d'avoir des choses terminées",
                 "env": "des choses terminées"},
                {"letter": "B", "label": "Fatigué(e) mais rechargé(e)",
                 "text": "Fatigué(e) mais rechargé(e). De bonnes interactions, "
                         "des apprentissages. La fatigue est bonne.",
                 "plain": "fatigué mais rechargé par les échanges",
                 "env": "fatigue mais recharge"},
                {"letter": "C", "label": "Besoin de calme",
                 "text": "Besoin de calme et de solitude. Les échanges de la semaine "
                         "demandent un grand silence.",
                 "plain": "besoin de calme après les échanges de la semaine",
                 "env": "besoin de calme"},
                {"letter": "D", "label": "Sentiment d'inachèvement",
                 "text": "Avec un sentiment d'inachèvement. "
                         "Tu vois déjà ce qu'il reste à faire.",
                 "plain": "tu vois déjà ce qu'il reste à faire",
                 "env": "sentiment d'inachèvement"},
            ],
        },
    ],
    "billet": [
        {"key": "environnement", "label": "Je me révèle dans un environnement :"},
        {"key": "vide", "label": "Ce qui me vide, c'est :"},
        {"key": "cadre_relationnel",
         "label": "Le cadre relationnel dans lequel je donne le meilleur :"},
        {"key": "rythme", "label": "Mon rythme naturel ressemble à :"},
    ],
}


SESSIONS: list[dict] = [_SESSION_0, _SESSION_1, _SESSION_2, _SESSION_3, _SESSION_4]


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

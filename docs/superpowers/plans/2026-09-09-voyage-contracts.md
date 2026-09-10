# Le voyage — Implementation contracts

Date: 2026-09-09
Status: **binding**. Reference document, not a plan.
Source of truth: `docs/superpowers/specs/2026-09-09-voyage-design.md` (authoritative), `CLAUDE.md`, `frontend/AGENTS.md`.

This file exists so six plan authors working in parallel cannot drift on names, types or JSON
shapes. Everything below is pinned. Where the spec already decided something it is transcribed
verbatim; where it left something genuinely underdetermined the line is marked **⚑ decided here**
and is listed in the *Decisions taken here* index at the end.

**How to use it.** Every phase plan quotes from this file rather than re-deriving a shape. If a
plan needs a name, a key or a type that is not here, that is a gap in this contract — raise it,
do not invent it locally.

**Rules that override everything below**

- App-facing French, code comments and commit messages English (`CLAUDE.md`).
- Ban list in user-facing French chrome: boussole, copilote, miroir, révélation, épanouissement,
  alignement, excellence, talent unique, vous vous démarquez. The ban applies to **app chrome**
  (hub, buttons, counselor UI, landing card). It does **not** apply to the cahier text reproduced
  verbatim inside the sessions and the portrait (spec decision 15) — e.g. session 4's own title
  « Le cadre qui te permet de te révéler » ships as written.
- Statuses are `String(16)`, never native enums (a MySQL ENUM widening is the one migration step
  this repo cannot rehearse locally).
- Prompts live in `PromptVersion`, never in code. Structure comes from a JSON-schema
  `output_config` passed via `extra_body`, never from prompt prose.
- Never hold a DB connection across an Anthropic stream: `db.session.remove()` before the stream,
  re-acquire after (`anthropic_service._run_analysis`).
- **Next.js**: `frontend/AGENTS.md` — "This is NOT the Next.js you know". Any plan step that
  touches a Next.js API (route files, `proxy.ts`, `params`, metadata, caching, `use cache`) must
  begin with a step telling the engineer to read the relevant guide under
  `frontend/node_modules/next/dist/docs/` **before** writing code.

---

## 0 · File manifest

New backend files:

```
backend/app/services/voyage/__init__.py            (empty)
backend/app/services/voyage/bank.py                § A
backend/app/services/voyage/scoring.py            § B
backend/app/services/voyage/generation.py         § G
backend/app/services/prompt_slots.py              § F
backend/app/models/voyage.py                      § C   (Voyage + VoyageNote, one file)
backend/app/routes/voyage.py                      § E
backend/migrations/versions/c9d0e1f2a3b4_add_voyages_table.py          § D
backend/migrations/versions/d0e1f2a3b4c5_add_voyage_notes_table.py     § D
backend/migrations/versions/e1f2a3b4c5d6_add_voyage_id_to_analyses.py  § D
backend/migrations/versions/f2a3b4c5d6e7_widen_prompt_version_path.py  § D
backend/seed_prompt_v10_voyage_micro.py
backend/seed_prompt_v10_voyage_portrait.py
backend/tests/test_voyage_bank.py
backend/tests/test_voyage_scoring.py
backend/tests/test_voyage_routes.py
backend/tests/test_voyage_prompt_context.py
backend/tests/test_voyage_generation.py
backend/tests/test_voyage_parity.py                ⚑ decided here — TS/Python drift guard,
                                                   same shape as tests/test_conditions_parity.py
backend/tests/test_prompt_slots.py
```

New frontend files:

```
frontend/src/types/voyage.ts                       § I
frontend/src/lib/voyage.ts                         ⚑ decided here — typed api.* wrappers
frontend/src/app/voyage/page.tsx
frontend/src/app/voyage/session/[n]/page.tsx
frontend/src/app/voyage/portrait/page.tsx
frontend/src/app/voyage/c/[token]/page.tsx
frontend/src/components/voyage/SessionProgress.tsx
frontend/src/components/voyage/SceneCard.tsx
frontend/src/components/voyage/OptionCard.tsx
frontend/src/components/voyage/ChecklistRow.tsx
frontend/src/components/voyage/BilletForm.tsx
frontend/src/components/voyage/MicroReveal.tsx
frontend/src/components/voyage/SynthesisSheet.tsx
frontend/src/components/voyage/RiasecBars.tsx
```

Modified files:

```
backend/app/__init__.py                register voyage_bp at /api/voyage; import the voyage model
backend/app/models/analysis.py         + voyage_id column, + "voyage_id" in to_dict()
backend/app/models/prompt_version.py   path String(1) -> String(16)
backend/app/routes/analyses.py         _merge_profile() voyage fold; Analysis(voyage_id=...)
backend/app/routes/prompts.py          _read_path() validates against prompt_slots
backend/app/routes/admin.py            + PUT /users/<id>/role, + stats["voyages"]
backend/app/services/anthropic_service.py  + _voyage_block(), called from _common_tail()
backend/tests/test_seed_scripts.py     regex (\w) -> (\w+), + the two voyage seeds
frontend/src/proxy.ts                  PROTECTED += "/voyage"
frontend/src/types/index.ts            AnalysisInputs._voyage/_voyage_id; Analysis.voyage_id;
                                       PromptVersion.path widened to PromptSlot
TEST-PLAN.md                           new « § 10 · Le voyage »
CLAUDE.md                              voyage section; "Portrait module" stays in Out of scope
```

---

## A · `backend/app/services/voyage/bank.py`

The single source of truth for text **and** weights. Pure data plus lookup helpers. No DB, no I/O,
no Flask import.

### A.1 Module constants

```python
SCORING_VERSION = "cahier-2026-09"          # exact value; also Voyage.scoring_version default

SESSION_IDS = ("0", "1", "2", "3", "4", "5")

KIND_CHECKLIST = "checklist"
KIND_SCENES = "scenes"

# Every key that carries a weight or an interpretation. public() strips all of them.
TAG_KEYS = ("riasec", "axes", "sdt", "schwartz", "big5", "style", "env", "risk", "sens")
PUBLIC_STRIP = TAG_KEYS + ("plain",)        # ⚑ decided here — `plain` is prompt-facing, never UI

RIASEC_LETTERS = ("R", "I", "A", "S", "E", "C")   # tie-break order, in this order
RIASEC_UNIVERS = {                                 # ⚑ decided here — lives in bank.py
    "R": "Réaliste",
    "I": "Investigateur",
    "A": "Artistique",
    "S": "Social",
    "E": "Entreprenant",
    "C": "Conventionnel",
}

SDT = ("autonomie", "appartenance", "competence")

SCHWARTZ = (
    "autodirection", "stimulation", "hedonisme", "reussite", "pouvoir", "securite",
    "conformite", "bienveillance", "universalisme", "integrite", "conservation",
)   # ⚑ decided here — exactly the eleven values the counselor manual's Dimension column uses,
    # ASCII snake_case like models/profile.py's SITUATIONS. A twelfth value is a bank bug.

BIG5 = ("ouverture", "conscienciosite", "extraversion", "agreabilite", "nevrotisme")

STYLES = ("holistique", "sequentiel", "adaptatif", "consultatif")

STYLE_PLAIN = {   # ⚑ decided here — what the prompt is allowed to say instead of the tag
    "holistique":  "part de l'ensemble et improvise",
    "sequentiel":  "avance par étapes structurées",
    "adaptatif":   "ajuste sa méthode au contexte",
    "consultatif": "s'appuie sur les autres pour décider",
}

RISK_LEVELS = ("Fort", "Modéré", "Calculé", "Faible")   # S5-1 only, manual's own casing

S4_SLOTS = ("espace", "rythme", "equipe", "manager", "irritant", "vendredi")
# S4-1 -> espace, S4-2 -> rythme, S4-3 -> equipe, S4-4 -> manager,
# S4-5 -> irritant, S4-6 -> vendredi. Position, not a tag.
```

### A.2 `AXES` — the ten S0 bipolar axes

```python
AXES: dict[str, dict[str, str]] = {
    "A1":  {"label": "Mobilité territoriale",
            "neg": "Ancrage local",              "pos": "Mobilité / international",
            "plain_neg": "rester près de chez elle",
            "plain_pos": "bouger, voir d'autres pays",
            "tension": "ancrage vs mobilité"},
    "A2":  {"label": "Visibilité",
            "neg": "Discrétion",                 "pos": "Reconnaissance publique",
            "plain_neg": "travailler dans l'ombre",
            "plain_pos": "être reconnue publiquement",
            "tension": "discrétion vs reconnaissance"},
    "A3":  {"label": "Rapport au collectif",
            "neg": "Indépendance / solo",        "pos": "Collectif / équipe",
            "plain_neg": "travailler seule",
            "plain_pos": "travailler en équipe",
            "tension": "solo vs collectif"},
    "A4":  {"label": "Échelle d'impact",
            "neg": "Impact local",               "pos": "Impact global / systémique",
            "plain_neg": "compter pour les gens autour d'elle",
            "plain_pos": "un impact visible",
            "tension": "impact local vs impact global"},
    "A5":  {"label": "Sécurité vs risque",
            "neg": "Stabilité / salariat",       "pos": "Risque / entrepreneuriat",
            "plain_neg": "un cadre stable",
            "plain_pos": "prendre des risques",
            "tension": "sécurité vs risque"},
    "A6":  {"label": "Type de création",
            "neg": "Organisation / méthode",     "pos": "Expression libre",
            "plain_neg": "organiser et planifier",
            "plain_pos": "créer librement",
            "tension": "méthode vs expression libre"},
    "A7":  {"label": "Nature du lien",
            "neg": "Systèmes / idées",           "pos": "Lien humain direct",
            "plain_neg": "les systèmes et les idées",
            "plain_pos": "le lien avec les gens",
            "tension": "idées vs personnes"},
    "A8":  {"label": "Temporalité de l'impact",
            "neg": "Long terme / différé",       "pos": "Impact immédiat / visible",
            "plain_neg": "construire sur la durée",
            "plain_pos": "voir le résultat tout de suite",
            "tension": "impact différé vs impact immédiat"},
    "A9":  {"label": "Rapport au corps",
            "neg": "Sédentaire / bureau",        "pos": "Terrain / action physique",
            "plain_neg": "le bureau et la réflexion",
            "plain_pos": "le terrain et l'action",
            "tension": "bureau vs terrain"},
    "A10": {"label": "Transmission vs expertise",
            "neg": "Expertise individuelle",     "pos": "Transmission / enseigner",
            "plain_neg": "maîtriser un domaine",
            "plain_pos": "transmettre",
            "tension": "expertise vs transmission"},
}
```

The S0 item → axis loadings, transcribed from the counselor manual's *Axe(s) principal(aux)*
column. This is the complete map; a bank that disagrees with it is wrong:

| item | axes | item | axes |
|---|---|---|---|
| `S0-01` | `[("A9", +1)]` | `S0-11` | `[("A5", -1)]` |
| `S0-02` | `[("A2", +1), ("A5", +1)]` | `S0-12` | `[("A2", +1), ("A4", +1)]` |
| `S0-03` | `[("A7", +1)]` | `S0-13` | `[("A3", -1)]` |
| `S0-04` | `[("A2", +1), ("A4", +1)]` | `S0-14` | `[("A3", +1)]` |
| `S0-05` | `[("A6", +1), ("A9", +1)]` | `S0-15` | `[("A4", +1)]` |
| `S0-06` | `[("A6", +1), ("A8", +1)]` | `S0-16` | `[("A8", +1), ("A10", +1)]` |
| `S0-07` | `[("A6", +1)]` | `S0-17` | `[("A6", -1)]` |
| `S0-08` | `[("A1", +1)]` | `S0-18` | `[("A7", +1)]` |
| `S0-09` | `[("A7", +1), ("A10", +1)]` | `S0-19` | `[("A5", +1)]` |
| `S0-10` | `[("A5", +1), ("A6", +1)]` | `S0-20` | `[("A4", -1), ("A7", +1)]` |

Resulting `n_items` per axis: A1 1 · A2 3 · A3 2 · A4 4 · A5 4 · A6 5 · A7 4 · A8 2 · A9 2 · A10 2.
A1 is the single-item axis that `TENSION_MIN_ITEMS` excludes (spec ⚑17).

**Exactly six keys per axis, all `str`, all mandatory, all non-empty:**

| key | audience | content |
|---|---|---|
| `label` | counselor sheet only | the manual's axis name |
| `neg` | counselor sheet only | the manual's negative pole |
| `pos` | counselor sheet only | the manual's positive pole |
| `plain_neg` | prompt + `_voyage` block | plain French, lowercase, no framework word |
| `plain_pos` | prompt + `_voyage` block | plain French, lowercase, no framework word |
| `tension` | prompt + `_voyage` block | « x vs y », lowercase, used when the axis is a tension |

⚑ decided here: `plain_neg` / `plain_pos` / `tension` are additions to the spec's three-key
sketch. They exist so `prompt_context()` never has to reach back into the bank and so the
`_voyage` block's literal example (« le terrain et l'action », « sécurité vs risque », « solo vs
collectif ») has one authoritative home. Keys `A1`…`A10`, exactly ten, no more.

### A.3 `SESSIONS` — the literal Python structure

`SESSIONS: list[dict]`, six entries, in order "0".."5".

**Session keys — exactly nine, all mandatory:**

```python
{
  "n":        str,          # "0".."5"
  "title":    str,          # French, verbatim cahier
  "subtitle": str,          # French, verbatim cahier
  "intro":    list[str],    # opening paragraphs, verbatim, one string per paragraph, may be []
  "outro":    list[str],    # ⚑ decided here — closing paragraphs, verbatim, may be []
  "duration": str,          # "5 min" | "15–20 min" | "20 min" | "15 min"
  "kind":     str,          # KIND_CHECKLIST (session 0) | KIND_SCENES (sessions 1-5)
  "items":    list[dict],   # checklist items (kind=checklist) or scenes (kind=scenes)
  "billet":   list[dict],   # exit-ticket fields, may be [] — in practice never is
}
```

Pinned headers (verbatim from `neoori_cahier_papier.pdf`, do not paraphrase):

| n | title | subtitle | duration | kind | items |
|---|---|---|---|---|---|
| 0 | `Dans 10 ans` | `Ta vision instinctive — 20 affirmations` | `5 min` | checklist | 20 |
| 1 | `Ce que tu faisais naturellement` | `Là où tout a commencé… · 6 scènes de ton enfance` | `15–20 min` | scenes | 6 |
| 2 | `Ce qui compte vraiment pour toi` | `Ce qui te donne envie de te lever le matin · 7 situations` | `20 min` | scenes | 7 |
| 3 | `Comment tu penses et tu fonctionnes` | `Pas ce que tu fais — comment tu le fais · 7 situations` | `20 min` | scenes | 7 |
| 4 | `Le cadre qui te permet de te révéler` | `Pas le métier — l'environnement · 6 situations` | `15 min` | scenes | 6 |
| 5 | `Ton rapport à ce qui n'existe pas encore` | `Risque · Sens · 7 situations` | `20 min` | scenes | 7 |

20 + 6 + 7 + 7 + 6 + 7 = **53 scored items**. Billet fields: 2 + 4 + 3 + 3 + 4 + 4 = **20**.

**Checklist item (session 0 only) — exactly three keys:**

```python
{"id": "S0-01",
 "text": "Travailler dehors, sur le terrain, en mouvement",
 "axes": [("A9", +1)]}

{"id": "S0-11",
 "text": "Avoir un emploi stable avec un salaire régulier",
 "axes": [("A5", -1)]}

{"id": "S0-20",
 "text": "Être utile à ma communauté locale",
 "axes": [("A4", -1), ("A7", +1)]}       # sign is per (axis, item) pair, not per item
```

- `id`: `str`, format `S0-NN` with **two-digit zero padding**, `S0-01` … `S0-20`.
- `text`: `str`, verbatim cahier, non-empty.
- `axes`: `list[tuple[str, int]]`, at least one entry, axis id ∈ `AXES`, sign ∈ `{+1, -1}`.
  An item may load on the same axis only once.

**Scene item (sessions 1–5) — exactly six keys:**

```python
{"id": "S1-1",
 "title": "La cabane",
 "subtitle": "Ce que tu construisais avec les autres",
 "narrative": ["Il y a des bouts de bois, des cartons, des couvertures usées.", "..."],
 "question": "À cet âge-là… tu te reconnaissais dans quel groupe ?",
 "options": [ ... ]}
```

- `id`: `str`, format `S<n>-<k>` with **no padding**, `S1-1` … `S1-6`, `S2-1` … `S2-7`,
  `S3-1` … `S3-7`, `S4-1` … `S4-6`, `S5-1` … `S5-7`. These are the counselor manual's own codes.
- `title`, `subtitle`, `question`: `str`, verbatim cahier, non-empty.
- `narrative`: `list[str]`, one string per paragraph, verbatim, may be `[]`.
- `options`: `list[dict]`, 4 to 8 entries.

**Option — four mandatory keys plus optional tag keys:**

```python
{"letter": "A",
 "label": "Les architectes",
 "text": "Ceux qui dessinaient le plan, qui avaient la vision.",
 "plain": "tu dessinais le plan, tu avais la vision",
 "riasec": {"R": 1, "I": 1, "E": 1, "C": 1}}
```

| key | type | mandatory | source | audience |
|---|---|---|---|---|
| `letter` | `str` | yes | cahier | UI |
| `label` | `str` | yes | counselor manual's *Option* column | UI |
| `text` | `str` | yes | cahier, verbatim | UI |
| `plain` | `str` | yes | authored | prompt only — stripped by `public()` |
| tag keys | see below | at least one per option | counselor manual's *Dimension* column | server only |

**Tag key vocabulary — the complete and closed list.** An option carries any subset; every option
carries at least one. A key not in `TAG_KEYS` is a bank bug and `test_voyage_bank.py` fails on it.

| key | type | allowed values | where it may appear |
|---|---|---|---|
| `riasec` | `dict[str, int]` | keys ∈ `RIASEC_LETTERS`; values positive `int`, 1 or 2 | S1 options (mandatory there) |
| `axes` | `list[tuple[str, int]]` | axis id ∈ `AXES`; sign ∈ `{+1, -1}` | **S0 checklist items only** |
| `sdt` | `str` | `autonomie` \| `appartenance` \| `competence` | any option |
| `schwartz` | `list[str]` | each ∈ `SCHWARTZ` | any option |
| `big5` | `dict[str, int]` | keys ∈ `BIG5`; values ∈ `{+1, -1}` ⚑ | any option |
| `style` | `str` | ∈ `STYLES` | S3 options (optional — an option may carry none) |
| `env` | `str` | free lowercase French noun phrase, 1–5 words, no trailing period | S4 options (mandatory there) |
| `risk` | `str` | S5-1: ∈ `RISK_LEVELS` (capitalised). S5-2 / S5-3: free short lowercase French label | S5-1/2/3 options (mandatory there) |
| `sens` | `str` | free short French label — see register table below | S5-4/5/6/7 options (mandatory there) |
| `plain` | `str` | free plain French, lowercase, second person for S1–S4 (« tu improvises, l'imprévu te réveille ») | every option (mandatory) |

⚑ decided here on `big5`: values are exactly `+1` or `-1`. The manual's « très haute » / « forte » /
« haute » all map to `+1`; « faible » / « basse » / « Introversion » map to `-1`. No magnitudes —
the Big Five level rule (net ≥ +2 / ≤ −2) is calibrated on ±1 counts.

⚑ decided here on `sdt` and `style`: single-valued (`str`), because the manual never names two of
either on one option. `schwartz` is a `list[str]` because it routinely names two
(« Conformité + Intégrité »).

⚑ decided here — `sens` register, per scene, so the `_voyage` block's lines read as French:

| scene | register | examples |
|---|---|---|
| S5-4 | noun phrase | `l'injustice`, `la bêtise`, `l'indifférence`, `le gâchis`, `la malhonnêteté`, `la violence` |
| S5-5 | noun phrase | `une trace visible`, `une trace dans les gens`, `une trace dans le système`, `pas besoin de trace`, `une trace discrète` |
| S5-6 | noun phrase | `le confort`, `la sécurité`, `le temps`, `les relations`, `rien, l'équilibre avant tout` |
| S5-7 | third-person clause | `elle crée`, `elle aide`, `elle comprend`, `elle gagne`, `elle est en harmonie`, `elle explore` |

**The S1 `riasec` map**, transcribed from the counselor manual's *Points attribués* column. This is
the whole of it, and it is the input `riasec_maxima()` is tested against — a slip here fails
`test_voyage_bank.py`, which is exactly what that test is for:

| scene | A | B | C | D | E | F | G | H |
|---|---|---|---|---|---|---|---|---|
| `S1-1` | R1 I1 E1 C1 | R2 C1 | R1 I1 | A2 C1 | S1 E1 | A1 I1 | — | — |
| `S1-2` | I2 C1 | R2 C1 | A2 S1 E1 | R1 S1 | I1 A2 | E2 S1 | — | — |
| `S1-3` | I2 R1 | I1 E2 | S2 R1 | R2 S1 | S2 C1 | E2 C1 | — | — |
| `S1-4` | R2 C1 | I2 E1 | A2 I1 | R1 E2 | C2 | S2 | — | — |
| `S1-5` | R2 C1 | I2 | A2 S1 | E2 R1 | S2 | E1 C2 | — | — |
| `S1-6` | I2 | R2 | A2 | R2 E1 | S2 | E1 C2 | S1 E2 | C2 |

Best-per-scene sums: R `2+2+2+2+2+2 = 12` · I `1+2+2+2+2+2 = 11` · A `2+2+0+2+2+2 = 10` ·
S `1+1+2+2+2+2 = 10` · E `1+2+2+2+2+2 = 11` · C `1+1+1+2+2+2 = 9`. S1-6 is the only eight-option
scene; every other scene has six.

**Billet field — exactly two keys:**

```python
{"key": "top3", "label": "Les 3 affirmations qui m'ont le plus parlé :"}
```

`key`: `str`, lowercase snake_case, unique **within its session**. `label`: `str`, verbatim cahier,
trailing « : » included. Pinned key sets:

| n | billet keys, in order |
|---|---|
| 0 | `top3`, `surprise` |
| 1 | `cabane`, `jeu`, `fierte`, `regard` |
| 2 | `vibrer`, `vide`, `vingt_ans` |
| 3 | `imprevu`, `meilleur`, `pression` |
| 4 | `environnement`, `vide`, `cadre_relationnel`, `rythme` |
| 5 | `risque`, `colere`, `trace`, `vivant` |

### A.4 Public functions

```python
def public() -> dict
def sessions() -> list[dict]
def session(n: str) -> dict                         # raises KeyError on an unknown id
def items(n: str) -> list[dict]
def item(item_id: str) -> dict | None
def item_ids(n: str) -> list[str]
def all_item_ids() -> list[str]                     # 53 ids, session order then item order
def option(item_id: str, letter: str) -> dict | None
def billet_keys(n: str) -> list[str]
def axis(axis_id: str) -> dict                      # raises KeyError on an unknown id
def axis_items(axis_id: str) -> list[tuple[str, int]]   # [(item_id, sign), ...]
def validate_answer(item_id: str, value) -> bool
def riasec_maxima() -> dict[str, int]
```

**`public()` — signature and stripping rule.**

```python
def public() -> dict:
    """The bank as GET /api/voyage/bank serves it: text only, no weights.

    Returns {"scoring_version": SCORING_VERSION, "sessions": [...]}, a deep copy of
    SESSIONS with every key in PUBLIC_STRIP removed at every depth. AXES is NOT
    included: axis names are scoring output, and decision 7 says the person never
    sees an axis, a trait or a framework name.
    """
```

Stripping rule, stated so a test can assert it literally: walk the returned structure; for every
`dict` encountered at any depth, no key may be a member of
`PUBLIC_STRIP == ("riasec", "axes", "sdt", "schwartz", "big5", "style", "env", "risk", "sens", "plain")`.
`test_voyage_bank.py` walks the JSON-serialised payload and asserts exactly that. `public()` returns
a **deep copy** — mutating the result must not touch `SESSIONS`.

**`validate_answer(item_id, value) -> bool`** — the rule `PUT /responses` enforces:

- `item_id` must exist in the bank, otherwise `False`.
- Session-0 item: `value` must be `True` or `False` (Python `bool`, JSON `true`/`false`).
  `0`/`1`/`"oui"` are rejected.
- Scene item: `value` must be a `str` equal to one of that scene's option `letter`s
  (case-sensitive, single uppercase character).

**`riasec_maxima() -> dict[str, int]`** — computed from `SESSIONS`, never a literal: for each S1
scene take the best available points per letter, sum across the six scenes.
`test_voyage_bank.py` asserts the result is exactly

```python
{"R": 12, "I": 11, "A": 10, "S": 10, "E": 11, "C": 9}
```

(The counselor manual prints E 10 / C 10; those two are transcription slips — spec ⚑17.)

---

## B · `backend/app/services/voyage/scoring.py`

Pure functions. No DB, no I/O, no Flask import, no bank mutation. `bank` is the only import.

### B.1 Module constants

```python
STAGE_S0 = "s0"
STAGE_VALIDATED = "validated"
STAGES = (STAGE_S0, STAGE_VALIDATED)

TENSION_BAND = (-2, 2)          # inclusive, on the resultant
TENSION_MIN_ITEMS = 2           # spec ⚑17 — excludes A1, which has one item

BIG5_HIGH = 2                   # net >= +2 -> "Élevé"
BIG5_LOW = -2                   # net <= -2 -> "Faible"
LEVEL_HIGH, LEVEL_MID, LEVEL_LOW = "Élevé", "Moyen", "Faible"

INTRO_EXTRA = {                 # ⚑ decided here — never the words the leak check bans
    "high": "plutôt tourné(e) vers les autres",
    "mid":  "à l'aise dans les deux registres",
    "low":  "plutôt tourné(e) vers l'intérieur",
}
```

### B.2 The `responses` type — one shape everywhere

Every function in this module takes the **full** responses object, exactly as
`Voyage.responses` returns it and exactly as `PUT /api/voyage/responses` accepts it:

```python
Responses = dict     # {"answers": {item_id: bool | str}, "billets": {session_id: {field: str}}}
```

Both top-level keys are always present (possibly empty). Scorers read `responses.get("answers", {})`
themselves. No function anywhere takes a bare answers dict.

### B.3 Signatures

```python
def score_s0(responses: dict) -> dict | None
def score_riasec(responses: dict) -> dict | None
def score_s2(responses: dict) -> dict | None
def score_s3(responses: dict) -> dict | None
def score_s4(responses: dict) -> dict | None
def score_s5(responses: dict) -> dict | None

def synthesize(responses: dict) -> dict
def prompt_context(synthesis: dict, micro_phrase: str | None, stage: str) -> list[str]

# helpers later phases call — pinned because routes and generation both use them
def missing_items(responses: dict, n: str) -> list[str]
def session_complete(responses: dict, n: str) -> bool
def completeness(responses: dict) -> dict[str, bool]
def chosen_option(responses: dict, item_id: str) -> dict | None
```

Every `score_*` returns `None` when its session is incomplete (any item of that session
unanswered). `synthesize()` never returns `None`.

### B.4 Return shapes, key by key

**`score_s0`**

```python
{
  "axes": {   # exactly ten keys, "A1".."A10", always all present even at zero — § B.5 has them all
      "A9": {"oui": 2, "non": 0, "resultant": 2, "n_items": 2, "tension": False},
  },
  "tensions": [                 # ordered by axis id, ascending; A1 can never appear
      {"axis": "A3", "resultant": 0, "label": "Rapport au collectif", "tension": "solo vs collectif"},
      {"axis": "A5", "resultant": 1, "label": "Sécurité vs risque",  "tension": "sécurité vs risque"},
  ],
  "top3": [                     # |resultant| desc, zero excluded, ties by axis id ascending, ≤ 3
      {"axis": "A9",  "resultant": 2, "pole": "pos",
       "label": "Terrain / action physique", "plain": "le terrain et l'action"},
      {"axis": "A10", "resultant": 2, "pole": "pos",
       "label": "Transmission / enseigner",  "plain": "transmettre"},
      {"axis": "A4",  "resultant": 2, "pole": "pos",
       "label": "Impact global / systémique","plain": "un impact visible"},
  ],
}
```

Rules: per item loading on an axis with sign *s*, OUI contributes `+s`, NON contributes `-s`.
`oui` / `non` are **counts of contributing items**, `resultant` is the signed sum.
`tension = TENSION_BAND[0] <= resultant <= TENSION_BAND[1] and n_items >= TENSION_MIN_ITEMS`.
`pole` is `"pos"` when `resultant > 0`, `"neg"` when `< 0`; `label` and `plain` are that pole's
`pos`/`plain_pos` or `neg`/`plain_neg`.

**`score_riasec`**

```python
{
  "scores":     {"R": 8, "I": 5, "A": 3, "S": 4, "E": 7, "C": 6},
  "maxima":     {"R": 12, "I": 11, "A": 10, "S": 10, "E": 11, "C": 9},
  "normalized": {"R": 0.667, "I": 0.455, "A": 0.3, "S": 0.4, "E": 0.636, "C": 0.667},
  "top3": [
      {"letter": "R", "univers": "Réaliste",     "score": 8, "normalized": 0.667},
      {"letter": "C", "univers": "Conventionnel","score": 6, "normalized": 0.667},
      {"letter": "E", "univers": "Entreprenant", "score": 7, "normalized": 0.636},
  ],
}
```

`normalized = round(score / maxima[letter], 3)` ⚑. `top3` sorts by `normalized` desc, ties broken
by `RIASEC_LETTERS` order (R I A S E C), always exactly three entries.

**`score_s2`**

```python
{
  "sdt":       {"autonomie": 3, "appartenance": 2, "competence": 1},   # all three, zero included
  "sdt_dominant": ["autonomie"],                 # all tied maxima, sorted by SDT order; no tie-break
  "schwartz":  {"bienveillance": 3, "universalisme": 2, "reussite": 1, "autodirection": 1},
                                                 # exactly the eleven SCHWARTZ keys, zeros
                                                 # included — § B.5 spells all eleven out
  "schwartz_dominant": ["bienveillance"],        # all tied maxima, sorted by SCHWARTZ order
  "ambivalences": {"item_id": "S2-7", "letter": "F",
                   "label": "Liberté / Indépendance",
                   "plain": "tu veux que ta vie t'appartienne"},
}
```

Counted over **S2-1 … S2-7 only**. Tags carried by options in other sessions are ignored here.
`ambivalences` is the S2-7 choice (spec), never `None` when the section is not `None`.

**`score_s3`**

```python
{
  "big5":   {"ouverture": 3, "conscienciosite": -1, "extraversion": 2,
             "agreabilite": 0, "nevrotisme": -2},          # signed nets, all five present
  "levels": {"ouverture": "Élevé", "conscienciosite": "Moyen", "extraversion": "Élevé",
             "agreabilite": "Moyen", "nevrotisme": "Faible"},
  "style":  {"holistique": 2, "sequentiel": 1, "adaptatif": 1, "consultatif": 3},
  "style_dominant": ["consultatif"],              # all tied maxima, sorted by STYLES order
  "intro_extra": "plutôt tourné(e) vers les autres",
}
```

Counted over **S3-1 … S3-7 only**. `intro_extra` is `INTRO_EXTRA["high"|"mid"|"low"]` on the sign
of the extraversion net using the same ±2 thresholds. `levels` values and `big5` trait names are
**counselor-facing only** — `prompt_context()` must never emit either.

**`score_s4`** — exactly six string keys, no arithmetic:

```python
{
  "espace":   "bureau fermé et calme",       # env of the chosen S4-1 option
  "rythme":   "cycles courts",               # S4-2
  "equipe":   "petite équipe soudée",        # S4-3
  "manager":  "confiance et droit à l'essai",# S4-4
  "irritant": "les interruptions constantes",# S4-5
  "vendredi": "besoin de calme",             # S4-6
}
```

**`score_s5`** — exactly seven string keys:

```python
{
  "risque":         "Calculé",                     # S5-1 risk, ∈ RISK_LEVELS
  "rapport_echec":  "elle analyse et recommence",  # ⚑ key name decided here — S5-2 risk
  "rapport_flou":   "elle crée son propre cadre",  # ⚑ key name decided here — S5-3 risk
  "valeur_centrale":"l'injustice",                 # S5-4 sens
  "trace":          "une trace dans les gens",     # S5-5 sens
  "sacrifice":      "le temps",                    # S5-6 sens
  "vivant":         "elle crée",                   # S5-7 sens
}
```

No combination rule across S5-1/2/3 is invented — the three labels sit side by side (spec).

### B.5 `synthesize()` — full literal return value

Phases 2, 4 and 5 all consume this. Every key below is mandatory; only the six section values may
be `None`. Values are illustrative but the shape is binding.

```python
{
  "scoring_version": "cahier-2026-09",

  "s0": {
    "axes": {
      "A1":  {"oui": 0, "non": 1, "resultant": -1, "n_items": 1,  "tension": False},
      "A2":  {"oui": 1, "non": 2, "resultant": -1, "n_items": 3,  "tension": True},
      "A3":  {"oui": 1, "non": 1, "resultant":  0, "n_items": 2,  "tension": True},
      "A4":  {"oui": 3, "non": 1, "resultant":  2, "n_items": 4,  "tension": True},
      "A5":  {"oui": 2, "non": 2, "resultant":  1, "n_items": 4,  "tension": True},
      "A6":  {"oui": 3, "non": 2, "resultant":  1, "n_items": 5,  "tension": True},
      "A7":  {"oui": 4, "non": 0, "resultant":  4, "n_items": 4,  "tension": False},
      "A8":  {"oui": 1, "non": 1, "resultant":  0, "n_items": 2,  "tension": True},
      "A9":  {"oui": 2, "non": 0, "resultant":  2, "n_items": 2,  "tension": True},
      "A10": {"oui": 2, "non": 0, "resultant":  2, "n_items": 2,  "tension": True},
    },
    "tensions": [
      {"axis": "A2",  "resultant": -1, "label": "Visibilité",
       "tension": "discrétion vs reconnaissance"},
      {"axis": "A3",  "resultant":  0, "label": "Rapport au collectif",
       "tension": "solo vs collectif"},
      {"axis": "A4",  "resultant":  2, "label": "Échelle d'impact",
       "tension": "impact local vs impact global"},
      {"axis": "A5",  "resultant":  1, "label": "Sécurité vs risque",
       "tension": "sécurité vs risque"},
      {"axis": "A6",  "resultant":  1, "label": "Type de création",
       "tension": "méthode vs expression libre"},
      {"axis": "A8",  "resultant":  0, "label": "Temporalité de l'impact",
       "tension": "impact différé vs impact immédiat"},
      {"axis": "A9",  "resultant":  2, "label": "Rapport au corps",
       "tension": "bureau vs terrain"},
      {"axis": "A10", "resultant":  2, "label": "Transmission vs expertise",
       "tension": "expertise vs transmission"},
    ],
    "top3": [
      {"axis": "A7",  "resultant": 4, "pole": "pos",
       "label": "Lien humain direct",        "plain": "le lien avec les gens"},
      {"axis": "A4",  "resultant": 2, "pole": "pos",
       "label": "Impact global / systémique","plain": "un impact visible"},
      {"axis": "A9",  "resultant": 2, "pole": "pos",
       "label": "Terrain / action physique", "plain": "le terrain et l'action"},
    ],
  },

  "riasec": {
    "scores":     {"R": 8, "I": 5, "A": 3, "S": 4, "E": 7, "C": 6},
    "maxima":     {"R": 12, "I": 11, "A": 10, "S": 10, "E": 11, "C": 9},
    "normalized": {"R": 0.667, "I": 0.455, "A": 0.3, "S": 0.4, "E": 0.636, "C": 0.667},
    "top3": [
      {"letter": "R", "univers": "Réaliste",      "score": 8, "normalized": 0.667},
      {"letter": "C", "univers": "Conventionnel", "score": 6, "normalized": 0.667},
      {"letter": "E", "univers": "Entreprenant",  "score": 7, "normalized": 0.636},
    ],
  },

  "s2": {
    "sdt": {"autonomie": 3, "appartenance": 2, "competence": 1},
    "sdt_dominant": ["autonomie"],
    "schwartz": {"autodirection": 2, "stimulation": 0, "hedonisme": 0, "reussite": 1,
                 "pouvoir": 0, "securite": 0, "conformite": 1, "bienveillance": 3,
                 "universalisme": 2, "integrite": 0, "conservation": 0},
    "schwartz_dominant": ["bienveillance"],
    "ambivalences": {"item_id": "S2-7", "letter": "F",
                     "label": "Liberté / Indépendance",
                     "plain": "tu veux que ta vie t'appartienne"},
  },

  "s3": {
    "big5": {"ouverture": 3, "conscienciosite": -1, "extraversion": 2,
             "agreabilite": 0, "nevrotisme": -2},
    "levels": {"ouverture": "Élevé", "conscienciosite": "Moyen", "extraversion": "Élevé",
               "agreabilite": "Moyen", "nevrotisme": "Faible"},
    "style": {"holistique": 2, "sequentiel": 1, "adaptatif": 1, "consultatif": 3},
    "style_dominant": ["consultatif"],
    "intro_extra": "plutôt tourné(e) vers les autres",
  },

  "s4": {
    "espace":   "bureau fermé et calme",
    "rythme":   "cycles courts",
    "equipe":   "petite équipe soudée",
    "manager":  "confiance et droit à l'essai",
    "irritant": "les interruptions constantes",
    "vendredi": "besoin de calme",
  },

  "s5": {
    "risque":          "Calculé",
    "rapport_echec":   "elle analyse et recommence",
    "rapport_flou":    "elle crée son propre cadre",
    "valeur_centrale": "l'injustice",
    "trace":           "une trace dans les gens",
    "sacrifice":       "le temps",
    "vivant":          "elle crée",
  },

  "completeness": {"0": True, "1": True, "2": True, "3": True, "4": True, "5": True},
}
```

Note the key is `riasec`, not `s1` (spec). `completeness` is `dict[str, bool]` keyed `"0"`.."`5`" ⚑.
An S0-only voyage yields `s0` filled and `riasec`/`s2`/`s3`/`s4`/`s5` all `None`, with
`completeness == {"0": True, "1": False, "2": False, "3": False, "4": False, "5": False}`.

### B.6 `prompt_context()` — contract

```python
def prompt_context(synthesis: dict, micro_phrase: str | None, stage: str) -> list[str]:
    """The reduced plain-French lines stored as Analysis.inputs["_voyage"].

    Returns CONTENT LINES ONLY — no "--- ... ---" header, no leading blank string.
    anthropic_service._voyage_block() adds those, exactly as _conditions_block()
    does for bloc 5.

    Pure over `synthesis`: it never reaches back into the bank. Every string it can
    emit is already present in the synthesis dict. That is what makes the
    "no numbers, no framework words" test enforceable.

    stage ∈ (STAGE_S0, STAGE_VALIDATED). Anything else is treated as STAGE_S0.
    A line whose value is empty or None is omitted entirely — the block never
    emits a label with nothing after it. Returns [] when nothing can be said.
    """
```

Hard invariants, each asserted by `test_voyage_prompt_context.py`:

1. No digit (`[0-9]`) appears anywhere in the returned lines.
2. None of the words in `generation.LEAK_PATTERNS` appears (diacritic-folded, word-boundary).
3. No `levels` value (`Élevé` / `Moyen` / `Faible`) and no `BIG5` trait name appears.
4. No `AXES[..]["label"]`, `["pos"]` or `["neg"]` appears — only `plain_pos`, `plain_neg`,
   `tension`.
5. `stage == STAGE_S0` emits at most the first two lines of § H; `stage == STAGE_VALIDATED`
   emits up to all nine.

`RIASEC_UNIVERS` values (Réaliste, Investigateur…) **are** allowed and are emitted at the validated
stage — the spec's literal block and the manual's restitution guide both name them. Do not "fix"
this.

---

## C · `backend/app/models/voyage.py`

One file, two models. Mirrors `models/profile.py` (encryption discipline) and
`models/counselor_note.py` (note shape).

### C.1 Module constants

```python
CONSENT_VERSION = "voyage-v1"

STATUS_EN_COURS, STATUS_S0, STATUS_TERMINE = "en_cours", "s0_termine", "termine"
STATUSES = (STATUS_EN_COURS, STATUS_S0, STATUS_TERMINE)
OPEN_STATUSES = (STATUS_EN_COURS, STATUS_S0)

MICRO_STATUSES = ("none", "generating", "success", "error")
PORTRAIT_STATUSES = ("none", "generating", "draft", "validated", "error")

PORTRAIT_KEYS = ("accroche", "qui_tu_es", "vibrer", "besoins", "chemins", "pas_encore")

LOCK_CODE    = "Avec un conseiller"          # spec, frontend section
LOCK_PROFILE = "Complétez votre profil"      # spec, frontend section
LOCK_ORDER   = "Terminez la session précédente"   # ⚑ decided here
```

### C.2 `Voyage` — columns

`__tablename__ = "voyages"`

| column | SQLAlchemy type | nullable | default / notes |
|---|---|---|---|
| `id` | `db.String(36)` | no | `primary_key=True, default=lambda: str(uuid4())` |
| `user_id` | `db.String(36)` | **no** | `db.ForeignKey("users.id"), index=True` — many per user |
| `status` | `db.String(16)` | no | `default=STATUS_EN_COURS, index=True` |
| `sessions_completed` | `db.JSON` | no | `default=list` — `list[str]` of `"0"`.."`5`" |
| `consent_at` | `db.DateTime` | **no** | set at creation; the voyage cannot exist without it |
| `consent_version` | `db.String(16)` | **no** | `default=CONSENT_VERSION` |
| `age_attested` | `db.Boolean` | no | `default=False` — must be `True` to create |
| `counselor_code_id` | `db.String(36)` | yes | `db.ForeignKey("counselor_codes.id")` — gates S1–S5 |
| `responses_encrypted` | `db.Text` | yes | Fernet token |
| `micro_status` | `db.String(16)` | no | `default="none"` |
| `micro_encrypted` | `db.Text` | yes | Fernet token |
| `portrait_status` | `db.String(16)` | no | `default="none"` |
| `portrait_encrypted` | `db.Text` | yes | Fernet token |
| `portrait_validated_at` | `db.DateTime` | yes | |
| `validated_by_id` | `db.String(36)` | yes | `db.ForeignKey("users.id")` |
| `share_token` | `db.String(64)` | yes | `unique=True, index=True` — set when S5 completes |
| `scoring_version` | `db.String(16)` | no | `default=bank.SCORING_VERSION` |
| `tokens_in` | `db.Integer` | yes | sum of both calls |
| `tokens_out` | `db.Integer` | yes | sum of both calls |
| `created_at` | `db.DateTime` | no | `default=datetime.utcnow` |
| `updated_at` | `db.DateTime` | no | `default=datetime.utcnow, onupdate=datetime.utcnow` |
| `completed_at` | `db.DateTime` | yes | set when S5 completes |

Relationships — **two FKs point at `users.id`, so both need `foreign_keys=`** or SQLAlchemy raises
`AmbiguousForeignKeysError` at mapper configuration (precedent: `PromptVersion.author`):

```python
user         = db.relationship("User", foreign_keys=[user_id])
validated_by = db.relationship("User", foreign_keys=[validated_by_id])
counselor_code = db.relationship("CounselorCode", foreign_keys=[counselor_code_id])
notes        = db.relationship("VoyageNote", backref="voyage",
                               lazy="dynamic", cascade="all, delete-orphan")
```

`sessions_completed` is a JSON column: **reassign a new list**, never `.append()` in place, or
SQLAlchemy will not see the change (same trap as `unlock_service`'s `new_inputs = dict(inputs)`).

### C.3 Encrypted payload shapes

`responses_encrypted` → `crypto.encrypt_json(...)` of:

```json
{"answers": {"S0-01": true, "S0-11": false, "S1-1": "A", "S5-7": "A"},
 "billets": {"0": {"top3": "…", "surprise": "…"},
             "1": {"cabane": "…", "jeu": "…", "fierte": "…", "regard": "…"}}}
```

⚑ decided here. The spec's data-model line sketches a flat `{item_id: value, "billets": {...}}`
map; its API line specifies `{answers: {...}, billets: {...}}`. The two-key form wins: it matches
the request body exactly, it cannot collide with an item id, and it means one shape flows
model → scoring → synthesis with no translation. `Voyage.responses` always returns both keys,
`{"answers": {}, "billets": {}}` when unset.

`micro_encrypted` →

```json
{"phrase": "…", "prompt_version_id": "…", "tokens_in": 412, "tokens_out": 38, "error": null}
```

`portrait_encrypted` →

```json
{"sections": {"accroche": "…", "qui_tu_es": "…", "vibrer": "…",
              "besoins": "…", "chemins": "…", "pas_encore": "…"},
 "snapshot": { …the full synthesize() dict, § B.5… },
 "flags": [],
 "edited": false,
 "prompt_version_id": "…",
 "tokens_in": 2140, "tokens_out": 980,
 "error": null}
```

⚑ decided here: the `error` key (spec names none). `str | None`, truncated to 500 chars, holding
the failure message that sets `*_status = "error"`. It lives inside the ciphertext so nothing
sensitive lands in a plaintext column; it is **never** exposed by `to_dict()` — only the status is.
`flags` is `list[str]`; the only value the code ever writes is `"vocabulaire"` (§ G).

### C.4 Properties and methods

```python
# ── encrypted accessors ──────────────────────────────────────────────────────
@property
def responses(self) -> dict                      # {"answers": {...}, "billets": {...}}
@responses.setter
def responses(self, value: dict | None) -> None

@property
def micro(self) -> dict                          # {} when unset
@micro.setter
def micro(self, value: dict | None) -> None

@property
def portrait(self) -> dict                       # {} when unset
@portrait.setter
def portrait(self, value: dict | None) -> None

# ── derived, candidate-safe ──────────────────────────────────────────────────
@property
def micro_phrase(self) -> str | None             # (self.micro or {}).get("phrase") or None
@property
def portrait_sections(self) -> dict[str, str]    # {} unless the 6 keys exist
@property
def is_open(self) -> bool                        # self.status in OPEN_STATUSES
@property
def has_code(self) -> bool                       # bool(self.counselor_code_id)

# ── scoring ──────────────────────────────────────────────────────────────────
def synthesis(self) -> dict                      # scoring.synthesize(self.responses)

# ── lookups ──────────────────────────────────────────────────────────────────
@classmethod
def open_for(cls, user_id: str) -> "Voyage | None"
@classmethod
def current_for(cls, user_id: str) -> "Voyage | None"
@classmethod
def latest_for(cls, user_id: str) -> "Voyage | None"
@classmethod
def by_token(cls, token: str) -> "Voyage | None"
@classmethod
def for_prompt(cls, user_id: str | None) -> "Voyage | None"

# ── serialisation ────────────────────────────────────────────────────────────
def to_dict(self) -> dict
```

Lookup semantics, pinned:

- `open_for` — the single row with `status in OPEN_STATUSES`, newest first. At most one exists;
  `POST /api/voyage` is what enforces that.
- `latest_for` — newest row by `created_at` desc, any status.
- `current_for` — `open_for(user_id) or latest_for(user_id)`. This is what `GET /api/voyage`
  serves.
- `by_token` — `filter_by(share_token=token).first()`; `None` for an empty/absent token.
- `for_prompt` — spec § Injection: newest row with `portrait_status == "validated"`; failing that,
  newest row with `micro_status == "success"`; failing that `None`. Returns `None` for
  `user_id is None`.

Decryption failures are **not** swallowed: `crypto.DecryptionError` propagates, exactly as
`SensitiveProfile.conditions` lets it.

### C.5 `to_dict()` — exactly twelve keys

```python
{
  "id": self.id,
  "status": self.status,                                      # STATUSES
  "sessions_completed": self.sessions_completed or [],        # list[str]
  "consent_at": self.consent_at.isoformat() if self.consent_at else None,
  "age_attested": bool(self.age_attested),
  "has_code": self.has_code,                                  # bool, NOT the code or its id
  "micro_status": self.micro_status,
  "micro_phrase": self.micro_phrase,                          # str | None
  "portrait_status": self.portrait_status,
  "share_token": self.share_token if self.status == STATUS_TERMINE else None,
  "created_at": self.created_at.isoformat(),
  "completed_at": self.completed_at.isoformat() if self.completed_at else None,
}
```

**FORBIDDEN from `to_dict()`** — adding any of these is a spec violation, and
`test_voyage_routes.py` asserts the key set is exactly the twelve above:

`responses`, `answers`, `billets`, any score or synthesis fragment, `portrait` sections,
`snapshot`, `flags`, `edited`, `error`, `user_id`, `counselor_code_id` (the id itself — only the
`has_code` boolean travels), `validated_by_id`, `portrait_validated_at`, `consent_version`,
`scoring_version`, `tokens_in`, `tokens_out`, `prompt_version_id`, `updated_at`,
and `share_token` while the status is not `termine`.

### C.6 `session_lock()` — module-level function

```python
def session_lock(voyage: "Voyage | None", profile, n: str) -> str | None:
    """The server-side session gate. Returns None when session `n` is open, else
    one of LOCK_CODE / LOCK_PROFILE / LOCK_ORDER — the exact French string the API
    returns as `error` and the UI renders on the locked card.

    `profile` is a models.profile.Profile or None.

    Rules (spec § API, "Session locking rule"):
      * no voyage                      -> LOCK_ORDER
      * n == "0"                       -> open once the voyage exists
      * n in "1".."5" and not has_code -> LOCK_CODE
      * n in "1".."5" and the profile lacks prenom or tranche_age -> LOCK_PROFILE
      * str(int(n) - 1) not in sessions_completed -> LOCK_ORDER
    Checked in that order; the first failing rule wins.
    """
```

`frontend/src/types/voyage.ts` mirrors this with the identical three strings;
`test_voyage_parity.py` reads the TS as text and asserts the strings match, exactly as
`test_conditions_parity.py` does for bloc 5.

### C.7 `VoyageNote`

`__tablename__ = "voyage_notes"`

| column | type | nullable | notes |
|---|---|---|---|
| `id` | `db.String(36)` | no | `primary_key=True, default=lambda: str(uuid4())` |
| `voyage_id` | `db.String(36)` | no | `db.ForeignKey("voyages.id", ondelete="CASCADE"), index=True` |
| `counselor_id` | `db.String(36)` | no | `db.ForeignKey("users.id")` |
| `body` | `db.Text` | yes | plaintext — a counselor's own note, not the person's data |
| `updated_at` | `db.DateTime` | no | `default=datetime.utcnow, onupdate=datetime.utcnow` |

`__table_args__ = (db.UniqueConstraint("voyage_id", "counselor_id", name="uq_voyage_notes_voyage_counselor"),)`

```python
def to_dict(self) -> dict:
    return {"id": self.id, "voyage_id": self.voyage_id,
            "body": self.body, "updated_at": self.updated_at.isoformat()}
```

Exactly four keys — mirrors `CounselorNote.to_dict()`.

---

## D · The four migrations

Chain from the current head `b8c9d0e1f2a3`. Ids follow the repo's hand-written rolling pattern
(`…a7b8c9d0e1f2` → `b8c9d0e1f2a3` → `c9d0e1f2a3b4` → …). **Assigned now; do not generate new ones.**

| # | revision | down_revision | filename | purpose |
|---|---|---|---|---|
| 1 | `c9d0e1f2a3b4` | `b8c9d0e1f2a3` | `c9d0e1f2a3b4_add_voyages_table.py` | create `voyages` (all 22 columns, FKs to `users` ×2 and `counselor_codes`, unique+index on `share_token`, index on `user_id` and `status`) |
| 2 | `d0e1f2a3b4c5` | `c9d0e1f2a3b4` | `d0e1f2a3b4c5_add_voyage_notes_table.py` | create `voyage_notes` (FK to `voyages` with `ondelete="CASCADE"`, unique `(voyage_id, counselor_id)`) |
| 3 | `e1f2a3b4c5d6` | `d0e1f2a3b4c5` | `e1f2a3b4c5d6_add_voyage_id_to_analyses.py` | add nullable `analyses.voyage_id` + FK `fk_analyses_voyage_id` + index |
| 4 | `f2a3b4c5d6e7` | `e1f2a3b4c5d6` | `f2a3b4c5d6e7_widen_prompt_version_path.py` | widen `prompt_versions.path` `String(1)` → `String(16)` |

New head after the four: **`f2a3b4c5d6e7`**.

House rules that apply to all four:

- Module docstring in English, ending with `Revision ID: …` / `Revises: …` / `Create Date: …`
  (see `e5f6a7b8c9d0_add_profile_tables.py`).
- Named constraints everywhere (`fk_voyages_user_id`, `uq_voyages_share_token`, …) — MySQL cannot
  drop an anonymous constraint on downgrade.
- Statuses are `sa.String(length=16)`. **No `sa.Enum` anywhere in these files.**
- Column alteration goes through `with op.batch_alter_table(...) as batch_op:` so the file runs on
  SQLite (precedent: `c3d4e5f6a7b8`).
- `downgrade()` fully reverses `upgrade()`. Migration 4's downgrade must first truncate any value
  longer than one character, or the narrowing fails on MySQL:
  `op.execute("UPDATE prompt_versions SET path = '1' WHERE LENGTH(path) > 1")` before the
  `alter_column` back to `String(1)`.
- Every migration round-trips **up and down on SQLite**. That is the acceptance test.

---

## E · The API

Blueprint `voyage_bp = Blueprint("voyage", __name__)`, registered in `app/__init__.py`:

```python
app.register_blueprint(voyage_bp, url_prefix="/api/voyage")
```

`app.url_map.strict_slashes = False` is global — do not add per-route slash handling.

**Count.** The spec's tables list 9 candidate rows + 5 counselor rows (one of which carries both
GET and PUT) + 1 admin = **16 handlers over 12 distinct paths**. The brief said "13 endpoints";
all 16 are pinned below and the discrepancy is listed in *Open questions*. Nothing was dropped.

Every response body is wrapped in a named key (`{"voyage": …}`, `{"bank": …}`), matching the rest
of the API. Every error body is `{"error": "<French sentence>"}` unless stated otherwise.
`403 → "Accès non autorisé."` is the repo's fixed string.

### Candidate endpoints — all `@jwt_required()`, owner-scoped

**E1 · `GET /api/voyage/bank`** — `@jwt_required()`

- Request: none.
- `200` → `{"bank": {"scoring_version": "cahier-2026-09", "sessions": [ …bank.public()… ]}}`
- No error path. Serves text only; a weight key in this payload is a test failure, not a runtime
  error.

**E2 · `GET /api/voyage`** — `@jwt_required()`

- Request: none.
- `200` → `{"voyage": <to_dict()>}` or `{"voyage": null}` when the user has never played.
  Uses `Voyage.current_for(user_id)`.

**E3 · `POST /api/voyage`** — `@jwt_required()`

- Request: `{"consent": true, "age_attested": true}` — both mandatory and both must be exactly
  `true`.
- `201` → `{"voyage": <to_dict()>}`; sets `consent_at=utcnow()`, `consent_version="voyage-v1"`,
  `status="en_cours"`, `sessions_completed=[]`, `scoring_version=SCORING_VERSION`.
- `400` `{"errors": ["Le consentement est requis."]}` when `consent is not True`.
- `400` `{"errors": ["Vous devez attester avoir 15 ans ou plus."]}` when `age_attested is not True`.
  Both failures at once return both strings in the `errors` array (mirrors
  `routes/profile.upsert_profile`).
- `409` `{"error": "Un voyage est déjà en cours."}` when `Voyage.open_for(user_id)` is not `None`.

**E4 · `GET /api/voyage/responses`** — `@jwt_required()`

- Request: none.
- `200` → `{"responses": {"answers": {...}, "billets": {...}}}` for the user's current voyage.
- `404` `{"error": "Aucun voyage en cours."}` when there is no voyage.

**E5 · `PUT /api/voyage/responses`** — `@jwt_required()`

- Request: `{"answers": {"S1-1": "A", "S0-03": true}, "billets": {"1": {"cabane": "…"}}}`.
  Both keys optional; a request with neither is a no-op `200`.
- Merge semantics: supplied ids overwrite, absent ids are untouched. Billets merge per session
  then per field.
- Unknown item ids are **dropped silently** (spec) — a stale client must not lose the whole save.
  Unknown billet session ids and unknown field keys are dropped the same way.
- `200` → `{"responses": {"answers": {…all…}, "billets": {…all…}}}` — the full merged set, so the
  player can reconcile after a lost connection. ⚑ decided here.
- `400` `{"errors": ["Réponse invalide pour S1-1."]}` — one string per known id whose value fails
  `bank.validate_answer`.
- `403` `{"error": "<LOCK_CODE|LOCK_PROFILE|LOCK_ORDER>"}` when any supplied id belongs to a locked
  session. Checked before any merge; nothing is written.
- `404` `{"error": "Aucun voyage en cours."}`.

**E6 · `POST /api/voyage/sessions/<n>/complete`** — `@jwt_required()`

Route: `@voyage_bp.post("/sessions/<n>/complete")`, `n` is the string `"0"`..`"5"`.

- Request: body ignored (billets are saved through E5).
- `200` → `{"voyage": <to_dict()>}`.
- Side effects: append `n` to `sessions_completed` (reassigned list, no duplicates);
  `n == "0"` → `status = "s0_termine"` and `generation.start_micro(voyage.id, current_app._get_current_object())`
  with `micro_status = "generating"`;
  `n == "5"` → `status = "termine"`, `completed_at = utcnow()`,
  `share_token = generate_share_token()` (`utils/tokens.py`, 32 chars) and
  `generation.start_portrait(...)` with `portrait_status = "generating"`.
  Sessions 1–4 change no status.
- `400` `{"errors": ["Réponses manquantes.", "S1-3", "S1-5"]}` — ⚑ decided here: `errors[0]` is the
  sentence, the remaining entries are the missing ids from `scoring.missing_items()`.
- `403` `{"error": "<LOCK_CODE|LOCK_PROFILE>"}`.
- `404` `{"error": "Aucun voyage en cours."}`.
- `409` `{"error": "Terminez la session précédente."}` (`LOCK_ORDER`) when S(n−1) is not complete,
  and the same `409` with `{"error": "Cette session est déjà terminée."}` when `n` is already in
  `sessions_completed`.
- `400` `{"error": "Session inconnue."}` when `n` is not in `bank.SESSION_IDS`.

**E7 · `POST /api/voyage/unlock`** — `@jwt_required()`

- Request: `{"code": "abcd-1234"}`. Normalised exactly as `analyses.unlock_with_code`:
  `re.sub(r"[^A-Za-z0-9]", "", raw).upper()`.
- `200` → `{"voyage": <to_dict()>}` with `has_code: true`; sets `counselor_code_id` and
  `code.uses_count += 1`.
- `400` `{"error": "Code requis."}` when the normalised code is empty.
- `400` `{"error": "Code invalide ou désactivé."}` when unknown or `is_active` is false.
- `404` `{"error": "Aucun voyage en cours."}`.
- `409` `{"error": "Ce voyage est déjà débloqué."}` when `counselor_code_id` is already set.
  `uses_count` is **not** incremented in that case.

**E8 · `GET /api/voyage/portrait`** — `@jwt_required()`

- Request: none.
- `200` → `{"portrait": {"sections": {…6 keys…}, "validated_at": "2026-09-12T10:04:00"}}`.
  Only when `portrait_status == "validated"`. Never carries `snapshot`, `flags` or `edited`.
- `404` `{"error": "Aucun voyage en cours."}`.
- `409` `{"error": "Votre portrait est en attente de validation.", "status": "draft"}` — the
  `status` key is part of the error body (spec: "else 409 `{status}`") and carries the current
  `portrait_status` (`none` | `generating` | `draft` | `error`).

**E9 · `DELETE /api/voyage`** — `@jwt_required()`

- Request: none. Erases the user's **current** voyage (open, else latest) and cascades its notes.
- `200` → `{"message": "Voyage supprimé."}`.
- `200` → `{"message": "Aucun voyage à supprimer."}` when there is none (mirrors
  `delete_profile`; deliberately not a 404).

### Counselor endpoints — `@role_required("counselor", "admin")` **and** the token

The synthesis sheet is never reachable by link alone (spec § Security). All five paths resolve the
voyage with `Voyage.by_token(token)`; a miss is `404 {"error": "Voyage introuvable."}`.

`CounselorPortrait` — one shape, five keys, returned by E10, E11, E12 and E13 ⚑ decided here:

```json
{"status": "draft",
 "sections": {"accroche": "…", "qui_tu_es": "…", "vibrer": "…",
              "besoins": "…", "chemins": "…", "pas_encore": "…"},
 "flags": [],
 "edited": false,
 "validated_at": null}
```

**E10 · `GET /api/voyage/c/<token>`**

- `200` → `{"voyage": {"id": "…", "status": "termine", "prenom": "Marie",
  "tranche_age": "25_34", "situation": "en_recherche",
  "synthesis": {…§ B.5…}, "portrait": {…CounselorPortrait…}}}`
  Exactly seven keys (⚑ `id` and `status` added to the spec's five, so the counselor UI knows
  whether S5 is done without a second call). `prenom` / `tranche_age` / `situation` come from the
  owner's `Profile`, `null` when absent.
- `403` `{"error": "Accès non autorisé."}` (from `@role_required`).
- `404` `{"error": "Voyage introuvable."}`.

**E11 · `PUT /api/voyage/c/<token>/portrait`**

- Request: `{"sections": {"accroche": "…", …all six keys…}}`.
- `200` → `{"portrait": {…CounselorPortrait…}}` with `edited: true`.
- `400` `{"errors": ["Section manquante ou vide : accroche."]}` — one string per missing or blank
  key. Extra keys are rejected: `{"errors": ["Section inconnue : intro."]}`.
- `403` `{"error": "Accès non autorisé."}`.
- `404` `{"error": "Voyage introuvable."}`.
- `409` `{"error": "Aucun portrait à modifier."}` when `portrait_status` is not `draft` or
  `validated`.

**E12 · `POST /api/voyage/c/<token>/portrait/regenerate`**

- Request: none.
- `202` → `{"portrait": {"status": "generating", "sections": {}, "flags": [], "edited": false,
  "validated_at": null}}`; sets `portrait_status = "generating"` and spawns
  `generation.start_portrait`.
- `403` / `404` as above.
- `409` `{"error": "Le portrait ne peut plus être régénéré."}` when `portrait_status != "draft"`.

**E13 · `POST /api/voyage/c/<token>/validate`**

- Request: none.
- `200` → `{"portrait": {…CounselorPortrait with status "validated" and validated_at set…}}`;
  sets `portrait_status = "validated"`, `portrait_validated_at = utcnow()`,
  `validated_by_id = get_jwt_identity()`.
- `403` / `404` as above.
- `409` `{"error": "Aucun portrait à valider."}` when `portrait_status != "draft"`.

**E14 · `GET /api/voyage/c/<token>/notes`**

- `200` → `{"note": {…VoyageNote.to_dict()…}}` or `{"note": null}`.
- `403` / `404` as above.

**E15 · `PUT /api/voyage/c/<token>/notes`**

- Request: `{"body": "…"}` (`""` is valid and clears the note text).
- `200` → `{"note": {…VoyageNote.to_dict()…}}`. Upsert keyed on
  `(voyage_id, counselor_id=get_jwt_identity())`.
- `403` / `404` as above.

### Admin

**E16 · `PUT /api/admin/users/<user_id>/role`** — `@admin_required`, in `routes/admin.py`

- Request: `{"role": "counselor"}`, one of `candidate` | `counselor` | `admin`.
- `200` → `{"user": <User.to_dict()>}`.
- `400` `{"error": "Rôle invalide."}` for any other value.
- `404` — `User.query.get_or_404(user_id)`.
- `409` `{"error": "Impossible de retirer le dernier rôle administrateur."}` ⚑ decided here, when
  the target is the only `admin` and the new role is not `admin`.

**`GET /api/admin/stats`** gains one key (no new endpoint):

```json
"voyages": {"started": 0, "s0_done": 0, "completed": 0, "validated": 0}
```

`started` = all rows; `s0_done` = `"0" in sessions_completed`, counted as
`status.in_(("s0_termine", "termine"))`; `completed` = `status == "termine"`;
`validated` = `portrait_status == "validated"`.

---

## F · `backend/app/services/prompt_slots.py`

⚑ decided here: the module lives beside `section_registry.py` and `tiers.py` in `app/services/`.
Its job is to be the single answer to "what may `PromptVersion.path` hold".

```python
"""Valid values for PromptVersion.path — parcours ids plus the voyage prompt slots.

Widened from String(1) to String(16) so the two voyage prompts do not have to
masquerade as parcours "4"/"5" everywhere the registry is iterated (spec 18).
"""
from . import section_registry as registry

VOYAGE_MICRO = "voyage_micro"
VOYAGE_PORTRAIT = "voyage_portrait"
VOYAGE_SLOTS = (VOYAGE_MICRO, VOYAGE_PORTRAIT)

LABELS = {
    "1": "Parcours 1 · J'ai une cible",
    "2": "Parcours 2 · Je cherche ma direction",
    "3": "Parcours 3 · Je pars de zéro",
    VOYAGE_MICRO: "Voyage · phrase (S0)",
    VOYAGE_PORTRAIT: "Voyage · portrait",
}

def valid() -> tuple[str, ...]:
    """('1', '2', '3', 'voyage_micro', 'voyage_portrait') — parcours ids first."""

def is_valid(slot) -> bool: ...
def is_voyage(slot) -> bool: ...
def normalize(slot) -> str: ...
def label(slot: str) -> str: ...
def choices() -> list[dict]:
    """[{"value": "1", "label": "Parcours 1 · J'ai une cible"}, ...] for the admin selector."""
```

Exact slot id strings — these five, nothing else:

```
"1"  "2"  "3"  "voyage_micro"  "voyage_portrait"
```

`"voyage_portrait"` is 15 characters; `String(16)` is the exact fit and the reason for that width.

`normalize(slot)`:
1. `str(slot or "").strip()`; empty → `registry.DEFAULT_PARCOURS` (`"1"`).
2. **Lowercase-compare against `VOYAGE_SLOTS` first** and return the slot verbatim on a hit.
3. Otherwise fall through to `registry.normalize(value.upper())`, which still folds the legacy
   `"A"`/`"B"` codes onto parcours ids.

Step 2 must precede any `.upper()` — `routes/prompts._read_path` currently uppercases before
validating, and `"VOYAGE_MICRO"` is not a slot. `_read_path` is rewritten to:

```python
def _read_path(raw):
    slot = prompt_slots.normalize(raw)
    if not prompt_slots.is_valid(slot):
        return None, (jsonify({"error": f"path doit être l'un de {_SLOTS_LABEL}."}), 400)
    return slot, None
```

`tests/test_seed_scripts.py`: the literal regex widens from `(\w)` to `(\w+)`, and `SEEDS` gains
`"seed_prompt_v10_voyage_micro.py": "voyage_micro"` and
`"seed_prompt_v10_voyage_portrait.py": "voyage_portrait"`. Its `registry.is_valid(value)` assertion
becomes `prompt_slots.is_valid(value)`.

---

## G · `backend/app/services/voyage/generation.py`

Reuses the analysis runner's shape: daemon thread, `db.session.remove()` before the stream, a
fresh session to write the result, status → `error` on failure. **The user message and the schema
are built before `db.session.remove()`**, never from an ORM object held across the stream.

### G.1 Module constants

```python
MICRO_SLOT = prompt_slots.VOYAGE_MICRO
PORTRAIT_SLOT = prompt_slots.VOYAGE_PORTRAIT

MICRO_MAX_TOKENS = 200
PORTRAIT_MAX_TOKENS = 3000
MICRO_WORDS = (15, 25)          # the manual's « 1 phrase, 15–25 mots »

PORTRAIT_KEYS = ("accroche", "qui_tu_es", "vibrer", "besoins", "chemins", "pas_encore")
PORTRAIT_TITLES = {             # the manual's page-20 template, in order
    "accroche":   "Phrase d'accroche",
    "qui_tu_es":  "Qui tu es",
    "vibrer":     "Ce qui te fait vibrer",
    "besoins":    "Ce dont tu as besoin",
    "chemins":    "Les chemins possibles",
    "pas_encore": "Ce que ton portrait ne dit pas encore",
}

FLAG_VOCABULAIRE = "vocabulaire"    # the only value ever written into portrait["flags"]
```

Model routing: `model, _ = tiers.model_for(tiers.FREE)` for micro and `tiers.model_for(tiers.PAID)`
for portrait — the tier's own `max_tokens` (8000) is **discarded**; the two constants above win.

### G.2 Entry points

```python
def start_micro(voyage_id: str, app) -> None:
    """Spawn a daemon thread running _run_micro. Returns immediately."""

def start_portrait(voyage_id: str, app) -> None:
    """Spawn a daemon thread running _run_portrait. Returns immediately."""

def _run_micro(voyage_id: str, app) -> None
def _run_portrait(voyage_id: str, app) -> None
```

Both `_run_*` follow `anthropic_service._run_analysis` step for step:

1. `with app.app_context():` load the row; missing → return.
2. `PromptVersion.query.filter_by(is_active=True, path=<SLOT>).first()`; missing → status `error`,
   payload `error = f"Aucun prompt actif pour le slot {slot}."`, commit, return.
3. Set status `generating`, record `prompt_version_id`, commit.
4. Capture `system_prompt`, `user_message`, `schema` into locals.
5. **`db.session.remove()`**.
6. Stream. `extra_body={"output_config": {"format": {"type": "json_schema", "schema": schema}}}`
   for the portrait only; the micro call is plain text with no schema. Catch
   `anthropic.BadRequestError` and retry once without `extra_body`, as `_run_analysis` does.
7. Re-query the row on a fresh connection and write the result.

No `ProgressReporter`: the voyage has no waiting screen with a bar. The hub polls
`GET /api/voyage` every 2 s while `micro_status == "generating"`.

### G.3 Message builders — pure, called before the stream

```python
def _micro_user_message(synthesis: dict, prenom: str | None) -> str
def _portrait_user_message(synthesis: dict, responses: dict, profile_fields: dict) -> str
```

`profile_fields` is a plain dict `{"prenom": ..., "tranche_age": ..., "situation": ..., "projet": ...}`
lifted off `Profile` before `db.session.remove()`.

**Exact section header strings.** Three for the portrait (spec), two for the micro (⚑ decided
here — `--- PROFIL DE BASE ---` is reused from `anthropic_service._profile_block`):

```
--- PROFIL DE BASE ---
--- SESSION 0 ---                 (micro only)
--- CE QUE TU AS CHOISI ---       (portrait only)
--- SYNTHÈSE ---                  (portrait only)
```

Micro message, literal shape:

```
--- PROFIL DE BASE ---
Prénom : Marie

--- SESSION 0 ---
Ce qui l'attire le plus : le lien avec les gens, un impact visible, le terrain et l'action
Autant coché des deux côtés sur : solo vs collectif · sécurité vs risque
```

`Prénom` is omitted when unknown. The attractions line joins `s0["top3"]` `plain` values with
`", "`. The tensions line joins `s0["tensions"]` `tension` values with `" · "` and is omitted when
there are none.

Portrait message, literal shape:

```
--- PROFIL DE BASE ---
Prénom : Marie
Tranche d'âge : 25_34
Situation actuelle : en_recherche
Projet : reprendre un travail au contact des gens

--- CE QUE TU AS CHOISI ---
La cabane : tu dessinais le plan, tu avais la vision
Le cours qu'on attendait : le temps disparaissait quand tu fabriquais quelque chose
…one line per scene, S1-1 through S5-7, 33 lines…

--- SYNTHÈSE ---
Univers dominants : Réaliste, Conventionnel, Entreprenant
Ce qui l'attire le plus dans dix ans : le lien avec les gens, un impact visible, le terrain et l'action
Autant coché des deux côtés sur : solo vs collectif · sécurité vs risque (à pondérer ×1,5)
Besoin dominant : autonomie
Façon de fonctionner : s'appuie sur les autres pour décider
Cadre : bureau fermé et calme · cycles courts · petite équipe soudée · confiance et droit à l'essai
Ce qui l'épuise : les interruptions constantes
Rapport au risque : Calculé
Ce qui la met en colère : l'injustice
La trace voulue : une trace dans les gens
Prête à sacrifier : le temps
Se sent vivant(e) quand : elle crée
```

`--- CE QUE TU AS CHOISI ---` uses the scene `title` as the line label and the chosen option's
`plain` as the value ⚑. Session 0 contributes nothing here — it reaches the model through
`--- SYNTHÈSE ---` only ⚑.

`Façon de fonctionner` uses `bank.STYLE_PLAIN[style]`, never the tag ⚑. **No number, no trait name
and no framework name appears anywhere in either message** — the same reduction discipline as bloc
5's `prompt_context()`. `Réaliste` / `Conventionnel` / `Entreprenant` and the SDT words
(`autonomie`, `appartenance`, `competence`) are the explicit exceptions: they are ordinary French
and the restitution guide names them out loud.

### G.4 The portrait output schema — exactly six keys

```python
def _portrait_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "accroche":   {"type": "string",
                           "description": "Une phrase. Une métaphore unique. Jamais « Tu es… ». "
                                          "Jamais un métier nommé."},
            "qui_tu_es":  {"type": "string",
                           "description": "5 à 7 phrases de prose. Mode de fonctionnement, énergie. "
                                          "Aucune liste."},
            "vibrer":     {"type": "string",
                           "description": "4 à 6 phrases de prose. Motivations, source d'énergie, sens."},
            "besoins":    {"type": "string",
                           "description": "5 à 7 phrases de prose. Cadre physique, cognitif et "
                                          "relationnel, formulé en préférences légitimes."},
            "chemins":    {"type": "string",
                           "description": "4 à 5 phrases de prose. Familles d'environnements — "
                                          "« les gens qui… », « les endroits où… ». Jamais un métier."},
            "pas_encore": {"type": "string",
                           "description": "1 à 2 phrases. Une question ouverte que les sessions ne "
                                          "tranchent pas."},
        },
        "required": ["accroche", "qui_tu_es", "vibrer", "besoins", "chemins", "pas_encore"],
        "additionalProperties": False,
    }
```

`test_voyage_generation.py` asserts `set(schema["properties"]) == set(PORTRAIT_KEYS)` and
`schema["required"] == list(PORTRAIT_KEYS)`.

### G.5 `leak_check()`

```python
def leak_check(sections: dict[str, str]) -> list[str]:
    """Framework vocabulary that survived into the portrait.

    Returns the offending words, lowercased, de-duplicated, sorted — [] when clean.
    Matching is word-boundary, case-insensitive, and diacritic-folded (NFD, combining
    marks dropped) on both the text and the pattern, so « névrotisme » and
    « nevrotisme » both hit one entry.
    """

LEAK_PATTERNS = (
    "névrotisme",
    "neuroticisme",
    "big five",
    "riasec",
    "schwartz",
    "sdt",
    "dunn",
    "kahneman",
    "dweck",
    "frankl",
    "logothérapie",
    "conscienciosité",
    "agréabilité",
    "extraversion",
    "introversion",
    "score",
    "trait",
)
```

Seventeen entries, exactly the spec's list. Word boundaries are what keep `trait` from firing
inside `portrait`. **`scoring.INTRO_EXTRA`, `bank.STYLE_PLAIN` and every `plain` / `plain_pos` /
`plain_neg` / `tension` string in the bank must be free of all seventeen** — that is why
`intro_extra` says « plutôt tourné(e) vers les autres » and not « extraversion ».

Retry protocol (spec): a non-empty result → one regeneration with an appended user turn quoting
the offending words → still non-empty → keep the draft and set
`portrait["flags"] = [FLAG_VOCABULAIRE]`. The counselor UI renders a warning banner off that flag.
`portrait_status` is `draft` either way.

---

## H · The `_voyage` block

Built in `backend/app/services/anthropic_service.py`, appended to **every** parcours message:

```python
def _voyage_block(inputs: dict) -> list[str]:
    """The voyage, already reduced to plain lines by scoring.prompt_context().

    Mirrors _conditions_block: the caller stores only the reduced lines, and this
    adds the blank separator and the header. Absent voyage -> [], no header.
    """
    lines = inputs.get("_voyage") or []
    if not lines:
        return []
    return ["", "--- CE QUE LE VOYAGE A RÉVÉLÉ ---"] + list(lines)


def _common_tail(inputs: dict) -> list[str]:
    return _conditions_block(inputs) + _rights_block(inputs) + _voyage_block(inputs)
```

`_common_tail` is already called by all three `_format_user_message_p*` — one change covers every
parcours.

**Exact French line labels.** Space before the colon, matching `_profile_block`'s
`f"Prénom : {…}"`. A line whose value would be empty is omitted entirely.

**`stage == "s0"` — literal example:**

```
--- CE QUE LE VOYAGE A RÉVÉLÉ ---
Phrase révélée : Tu cherches des endroits où ce que tu fabriques sert vraiment à quelqu'un.
Ce qui l'attire le plus dans dix ans : le terrain et l'action, transmettre, un impact visible
```

**`stage == "validated"` — literal example (the two lines above, then seven more):**

```
--- CE QUE LE VOYAGE A RÉVÉLÉ ---
Phrase révélée : Tu cherches des endroits où ce que tu fabriques sert vraiment à quelqu'un.
Ce qui l'attire le plus dans dix ans : le terrain et l'action, transmettre, un impact visible
Univers dominants : Réaliste, Entreprenant, Investigateur
Besoin dominant : autonomie
Ambivalences relevées : sécurité vs risque · solo vs collectif
Cadre où elle donne le meilleur : bureau fermé et calme · cycles courts · petite équipe soudée
Ce qui l'épuise : les interruptions constantes
Ce qui la met en colère : l'injustice
Se sent vivant(e) quand : elle crée
```

Label table — these nine strings, verbatim, in this order:

| # | label | stage | source | join |
|---|---|---|---|---|
| 1 | `Phrase révélée : ` | both | `micro_phrase` | — |
| 2 | `Ce qui l'attire le plus dans dix ans : ` | both | `s0["top3"][*]["plain"]` | `", "` |
| 3 | `Univers dominants : ` | validated | `riasec["top3"][*]["univers"]` | `", "` |
| 4 | `Besoin dominant : ` | validated | `s2["sdt_dominant"]` | `", "` |
| 5 | `Ambivalences relevées : ` | validated | `s0["tensions"][*]["tension"]` | `" · "` |
| 6 | `Cadre où elle donne le meilleur : ` | validated | `s4["espace"]`, `s4["rythme"]`, `s4["equipe"]` | `" · "` |
| 7 | `Ce qui l'épuise : ` | validated | `s4["irritant"]` | — |
| 8 | `Ce qui la met en colère : ` | validated | `s5["valeur_centrale"]` | — |
| 9 | `Se sent vivant(e) quand : ` | validated | `s5["vivant"]` | — |

The header is `--- CE QUE LE VOYAGE A RÉVÉLÉ ---`, exactly. Both it and « Phrase révélée » share a
root with the banned « révélation »; they are **model-facing prompt text, not UI chrome**, so the
ban does not reach them — but the Phase-3 hub must not label the micro-phrase that way. Use
« Votre phrase » or « Ce que la session 0 dit » in the UI.

Wiring in `routes/analyses._merge_profile()`, after the profile fold (spec § Injection):

```python
voyage = Voyage.for_prompt(user_id)
if voyage:
    inputs["_voyage_id"] = voyage.id
    stage = STAGE_VALIDATED if voyage.portrait_status == "validated" else STAGE_S0
    inputs["_voyage"] = prompt_context(voyage.synthesis(), voyage.micro_phrase, stage)
```

`create_analysis()` then passes `voyage_id=inputs.get("_voyage_id")` to the `Analysis(...)`
constructor. The rapport page and `/c/<token>` do **not** render `_voyage`.

---

## I · `frontend/src/types/voyage.ts`

Mirrors § E key for key. No French copy is duplicated here except the two constants marked below —
the 53 items' text always comes from the API.

```ts
/**
 * Le voyage — API types.
 *
 * Mirrors backend/app/models/voyage.py and backend/app/routes/voyage.py. Bank
 * shapes come from GET /api/voyage/bank; nothing in the cahier is re-typed here.
 */

export type VoyageStatus = "en_cours" | "s0_termine" | "termine"
export type MicroStatus = "none" | "generating" | "success" | "error"
export type PortraitStatus = "none" | "generating" | "draft" | "validated" | "error"
export type SessionId = "0" | "1" | "2" | "3" | "4" | "5"
export type SessionKind = "checklist" | "scenes"
export type PortraitKey =
  | "accroche" | "qui_tu_es" | "vibrer" | "besoins" | "chemins" | "pas_encore"

// ── bank (GET /api/voyage/bank) ──────────────────────────────────────────────
export interface BankBilletField { key: string; label: string }
export interface BankChecklistItem { id: string; text: string }
export interface BankOption { letter: string; label: string; text: string }
export interface BankScene {
  id: string
  title: string
  subtitle: string
  narrative: string[]
  question: string
  options: BankOption[]
}
export type BankItem = BankChecklistItem | BankScene
export interface BankSession {
  n: SessionId
  title: string
  subtitle: string
  intro: string[]
  outro: string[]
  duration: string
  kind: SessionKind
  items: BankItem[]
  billet: BankBilletField[]
}
export interface Bank { scoring_version: string; sessions: BankSession[] }
export interface BankResponse { bank: Bank }

export const isScene = (item: BankItem): item is BankScene => "options" in item

// ── voyage (GET/POST /api/voyage) ────────────────────────────────────────────
export interface Voyage {
  id: string
  status: VoyageStatus
  sessions_completed: SessionId[]
  consent_at: string | null
  age_attested: boolean
  has_code: boolean
  micro_status: MicroStatus
  micro_phrase: string | null
  portrait_status: PortraitStatus
  share_token: string | null
  created_at: string
  completed_at: string | null
}
export interface VoyageResponse { voyage: Voyage | null }

// ── responses (GET/PUT /api/voyage/responses) ────────────────────────────────
export type VoyageAnswer = boolean | string
export interface VoyageResponses {
  answers: Record<string, VoyageAnswer>
  billets: Record<string, Record<string, string>>
}
export interface ResponsesResponse { responses: VoyageResponses }

// ── portrait (GET /api/voyage/portrait) ──────────────────────────────────────
export type PortraitSections = Record<PortraitKey, string>
export interface CandidatePortrait {
  sections: PortraitSections
  validated_at: string | null
}
export interface CandidatePortraitResponse { portrait: CandidatePortrait }

// ── counselor (GET /api/voyage/c/[token] and friends) ────────────────────────
export interface CounselorPortrait {
  status: PortraitStatus
  sections: Partial<PortraitSections>
  flags: string[]
  edited: boolean
  validated_at: string | null
}
export interface CounselorPortraitResponse { portrait: CounselorPortrait }

export interface AxisScore {
  oui: number; non: number; resultant: number; n_items: number; tension: boolean
}
export interface AxisTension {
  axis: string; resultant: number; label: string; tension: string
}
export interface AxisTop {
  axis: string; resultant: number; pole: "pos" | "neg"; label: string; plain: string
}
export interface RiasecTop {
  letter: string; univers: string; score: number; normalized: number
}
export interface S0Score {
  axes: Record<string, AxisScore>
  tensions: AxisTension[]
  top3: AxisTop[]
}
export interface RiasecScore {
  scores: Record<string, number>
  maxima: Record<string, number>
  normalized: Record<string, number>
  top3: RiasecTop[]
}
export interface S2Score {
  sdt: Record<string, number>
  sdt_dominant: string[]
  schwartz: Record<string, number>
  schwartz_dominant: string[]
  ambivalences: { item_id: string; letter: string; label: string; plain: string }
}
export interface S3Score {
  big5: Record<string, number>
  levels: Record<string, string>
  style: Record<string, number>
  style_dominant: string[]
  intro_extra: string
}
export interface S4Score {
  espace: string; rythme: string; equipe: string
  manager: string; irritant: string; vendredi: string
}
export interface S5Score {
  risque: string; rapport_echec: string; rapport_flou: string
  valeur_centrale: string; trace: string; sacrifice: string; vivant: string
}
export interface VoyageSynthesis {
  scoring_version: string
  s0: S0Score | null
  riasec: RiasecScore | null
  s2: S2Score | null
  s3: S3Score | null
  s4: S4Score | null
  s5: S5Score | null
  completeness: Record<SessionId, boolean>
}

export interface CounselorVoyage {
  id: string
  status: VoyageStatus
  prenom: string | null
  tranche_age: string | null
  situation: string | null
  synthesis: VoyageSynthesis
  portrait: CounselorPortrait
}
export interface CounselorVoyageResponse { voyage: CounselorVoyage }

export interface VoyageNote {
  id: string
  voyage_id: string
  body: string | null
  updated_at: string
}
export interface VoyageNoteResponse { note: VoyageNote | null }

// ── the two French constants that legitimately live here ─────────────────────

/** Section keys + titles for the portrait, in order. Mirrors
 *  backend/app/services/voyage/generation.py PORTRAIT_TITLES — the API returns the
 *  six bodies keyed but untitled, and both the candidate page and the counselor
 *  editor need the headings. test_voyage_parity.py asserts the two lists match. */
export const PORTRAIT_SECTIONS: { key: PortraitKey; title: string }[] = [
  { key: "accroche",   title: "Phrase d'accroche" },
  { key: "qui_tu_es",  title: "Qui tu es" },
  { key: "vibrer",     title: "Ce qui te fait vibrer" },
  { key: "besoins",    title: "Ce dont tu as besoin" },
  { key: "chemins",    title: "Les chemins possibles" },
  { key: "pas_encore", title: "Ce que ton portrait ne dit pas encore" },
]

/** The three lock reasons, byte-identical to session_lock() in
 *  backend/app/models/voyage.py. The hub renders these on a locked card; the API
 *  returns the same string as `error` on a 403. */
export const LOCK_CODE = "Avec un conseiller"
export const LOCK_PROFILE = "Complétez votre profil"
export const LOCK_ORDER = "Terminez la session précédente"

/** Client-side mirror of models/voyage.session_lock(). Same order of checks. */
export function sessionLock(
  voyage: Voyage | null,
  profile: { prenom?: string | null; tranche_age?: string | null } | null,
  n: SessionId,
): string | null
```

Additions to `frontend/src/types/index.ts`:

```ts
export type PromptSlot = Parcours | "voyage_micro" | "voyage_portrait"
// PromptVersion.path becomes `path?: PromptSlot | "A" | "B"`

// AnalysisInputs gains:
  /** Voyage traceability — the voyage that fed this analysis. */
  _voyage_id?: string
  /** Reduced plain-French lines, no numbers, no framework words. Model-facing
   *  only: the report and /c/<token> never render this. */
  _voyage?: string[]

// Analysis gains:
  voyage_id?: string | null
```

`frontend/src/proxy.ts`: `const PROTECTED = ["/admin", "/profil", "/voyage"]`.

---

## J · Naming conventions

**French route segments, English identifiers.** The URL is product surface; the code is not.

| layer | language | examples |
|---|---|---|
| Next.js routes | French | `/voyage`, `/voyage/session/[n]`, `/voyage/portrait`, `/voyage/c/[token]` |
| API paths | French | `/api/voyage`, `/api/voyage/bank`, `/api/voyage/responses`, `/api/voyage/sessions/<n>/complete`, `/api/voyage/unlock`, `/api/voyage/portrait`, `/api/voyage/c/<token>` |
| Python modules, functions, variables | English | `voyage/bank.py`, `start_portrait`, `leak_check`, `session_lock`, `missing_items` |
| TS files, components, hooks | English | `voyage.ts`, `SessionProgress`, `SynthesisSheet`, `sessionLock` |
| Domain nouns that have no English equivalent | French, in code | `voyage`, `billet`, `parcours`, `prenom`, `tranche_age`, `cible_visee` |
| Enum / tag values in data | French, ASCII snake_case, unaccented | `en_cours`, `s0_termine`, `autonomie`, `conscienciosite`, `sequentiel` |
| User-visible strings | French | everything rendered, plus every API `error` / `errors` string |
| Comments, docstrings, commit messages | English | — |

Blueprint name `voyage`, table names `voyages` / `voyage_notes`, model classes `Voyage` /
`VoyageNote`, service package `app/services/voyage/`.

**Test file names** — one per contract area, `backend/tests/`:

```
test_voyage_bank.py            § A     53 items, unique ids, tags in vocabulary,
                                       riasec_maxima() == R12 I11 A10 S10 E11 C9,
                                       every S0 item loads on ≥ 1 axis,
                                       public() carries no PUBLIC_STRIP key
test_voyage_scoring.py         § B     reversed items, tension band, A1 never a tension,
                                       the manual's RIASEC worked example, ties as lists,
                                       Big Five thresholds, S5 mapping, incomplete -> None
test_voyage_routes.py          § E     consent + age, owner-only, id/value validation,
                                       complete needs all items and order, S1 locks,
                                       unlock increments uses_count, S5 sets share_token and
                                       spawns generation (mocked), portrait 409 until validated,
                                       counselor 403 for candidates, validate flips status,
                                       DELETE erases, ciphertext at rest, to_dict key set
test_voyage_prompt_context.py  § H     no digits, no banned words, s0 vs validated stage,
                                       absent voyage -> no block, all three parcours include it
test_voyage_generation.py      § G     six-key schema, leak check -> retry -> flag,
                                       missing slot prompt -> error
test_voyage_parity.py          § C/I   the three lock strings and PORTRAIT_SECTIONS match
                                       between Python and TypeScript
test_prompt_slots.py           § F     valid(), normalize() on legacy A/B and on the two slots
```

Run from `/Users/imran/Downloads/design_handoff_cv_analyzer/backend` with `pytest`. Fixtures
`app`, `client`, `admin_headers` come from `tests/conftest.py`; a logged-in candidate is built the
way `test_profile.py::auth` does (`create_access_token(identity=..., additional_claims={"role": ...})`
— `TestingConfig` puts the JWT in headers, not cookies).

**Frontend verification** — there is no test runner. `npm run lint` and `npm run build` from
`frontend/`, plus rows added to `TEST-PLAN.md` § 10 in the existing `| # | Do | Expect |` format.

**Commit message prefixes** — Conventional Commits, English subject, lowercase, no trailing period,
scope `voyage` (the repo's scopes are French domain nouns: `parcours 1`, `profil`, `prompts`):

```
feat(voyage): …        new behaviour       e.g. feat(voyage): score the five frameworks the cahier defines
fix(voyage): …         defect
test(voyage): …        tests only
refactor(voyage): …    no behaviour change
chore(voyage): …       seeds, config, docs
docs(voyage): …        TEST-PLAN / CLAUDE.md
```

One phase can be several commits; each commit must leave `pytest` green and `npm run build`
passing, because `git push` on `initial` deploys.

---

## Decisions taken here (⚑)

Every line marked ⚑ above, collected. These fill gaps the spec left open; none contradicts it.

1. `public()` strips `plain` as well as the nine tag keys — `plain` is prompt-facing, never UI.
2. `public()` returns `{"scoring_version", "sessions"}` and excludes `AXES`; the endpoint wraps it
   in `{"bank": …}`.
3. `AXES` entries carry six keys, adding `plain_neg`, `plain_pos` and `tension` so
   `prompt_context()` never touches the bank and the block's literal wording has one home.
4. `RIASEC_UNIVERS` and `STYLE_PLAIN` live in `bank.py`; `riasec_maxima()` lives in `bank.py`.
5. `SCHWARTZ` is exactly the eleven values the manual uses; `big5` values are exactly ±1;
   `sdt` and `style` are single-valued, `schwartz` is a list.
6. `sens` register is pinned per S5 scene; `env` is a free lowercase French noun phrase;
   `risk` is closed on S5-1 and free on S5-2/S5-3.
7. Sessions carry an `outro` list so the cahier's closing paragraphs have a home.
8. Billet key sets are pinned per session (20 fields total).
9. Stored responses are `{"answers": {...}, "billets": {...}}`, not the spec's flat sketch; every
   scoring function takes that same full object.
10. `completeness` is `dict[str, bool]` keyed `"0"`..`"5"`; `normalized` is rounded to 3 decimals.
11. `score_s5` key names `rapport_echec` and `rapport_flou`; `INTRO_EXTRA`'s three strings.
12. `prompt_context()` returns content lines only; `_voyage_block()` adds the blank line and the
    header, mirroring `_conditions_block`.
13. Encrypted payloads gain an `error` key (≤ 500 chars), never exposed by `to_dict()`.
14. `session_lock()` lives in `models/voyage.py`; `LOCK_ORDER = "Terminez la session précédente"`.
15. The four migration ids, filenames and their order.
16. One `CounselorPortrait` shape with five keys (adds `validated_at`) for E10–E13;
    `GET /c/<token>` returns seven keys (adds `id` and `status`).
17. `PUT /responses` returns the full merged set; `POST /sessions/<n>/complete` returns the missing
    ids in `errors[1:]`; `POST regenerate` returns `202`.
18. Every French error string in § E.
19. `PUT /admin/users/<id>/role` refuses to demote the last admin (`409`).
20. `prompt_slots.py` lives in `app/services/`; `normalize()` checks the voyage slots before
    uppercasing.
21. Micro message headers `--- PROFIL DE BASE ---` / `--- SESSION 0 ---`; the portrait's
    `--- CE QUE TU AS CHOISI ---` uses the scene title as the label and omits session 0.
22. `leak_check` folds diacritics rather than doubling the pattern list.
23. `Analysis.to_dict()` gains `"voyage_id"`, mirroring `prompt_version_id`.
24. `_common_tail()` gains `_voyage_block()` — one change covers all three parcours.
25. `PORTRAIT_SECTIONS` and the three lock strings are the only French duplicated into TS, guarded
    by `test_voyage_parity.py`; `frontend/src/lib/voyage.ts` holds the typed API wrappers.

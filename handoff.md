# Handoff — Piece #3 : Chemin B (Portrait de potentiel)

> This document is self-contained. A fresh AI session should be able to pick up this task with no prior conversation context. Read it end-to-end before touching code.

---

## 0. TL;DR

The PM delivered a v1.7 UX prototype that introduces a **second user path** called **Chemin B**: an orientation tool for people who do **not** have an established CV (young, returning to work after a long pause, returning after illness/handicap). It produces a **5-section "Portrait de potentiel"** instead of the existing 9-section CV analysis.

Pieces #1 (prompt v1.7-A) and #2 (bifurcation landing page) have already shipped. The landing now shows two cards — Chemin A (active) and Chemin B (disabled, "Bientôt"). **This piece activates Chemin B.**

Scope: new prompt in DB, new form route, new analysis flow, partial rapport view changes. No schema migration required (the `Analysis.inputs` JSON column is reused with a path discriminator).

---

## 1. Project context (read this first)

**neoori** is a French CV analysis tool. Repo at `/Users/imran/Downloads/design_handoff_cv_analyzer/`.

| Layer | Stack | Path |
|---|---|---|
| Frontend | Next.js 15 (App Router, TypeScript), Tailwind, shadcn/ui | `frontend/` |
| Backend | Flask + SQLAlchemy + Flask-JWT-Extended | `backend/` |
| DB | TiDB Cloud (MySQL-compatible) | — |
| AI | Anthropic SDK, two-tier routing (haiku free / sonnet paid) | `backend/app/services/anthropic_service.py` |
| Prompt storage | DB table `prompt_versions`, edited via `/admin/prompts` UI, never in code | `backend/app/models/prompt_version.py` |

Live URLs:
- Frontend: `https://frontend-seven-fawn-59.vercel.app` (auto-deploy on push to `initial` branch)
- Backend: `https://neoori-cv-analyser.onrender.com` (auto-deploy on push to `initial` branch)
- Browser → Vercel rewrites `/api/*` → Render. JWT cookies are `SameSite=Lax`.

**Read these before editing:**
- `CLAUDE.md` at repo root — project rules, the 8 form fields for Chemin A, the 9 analysis sections, design tokens, copy rules ("no boussole, copilote, miroir…"), French-only UI rule
- `frontend/AGENTS.md` — Next.js version warning ("APIs may differ from your training data, read `node_modules/next/dist/docs/` before writing code")
- `backend/app/services/anthropic_service.py` — the analysis runner (uses `client.messages.stream` inside a background daemon thread; frontend polls `GET /analyses/<id>`)
- `backend/app/routes/analyses.py` — the analysis HTTP routes

**Language rule (critical):**
- UI strings = **French** (all of them, including new ones in this piece)
- Code comments + commit messages = English
- Copy ban list: boussole, copilote, miroir, révélation, épanouissement, alignement, excellence, talent unique, vous vous démarquez
- Ton: factual, sober, professional, direct, vouvoiement systématique

---

## 2. What pieces #1 + #2 already shipped (do NOT redo)

### Piece #1 — Prompt v1.7-A
- New file: `backend/seed_prompt_v17.py` — seeds prompt v1.7 for Chemin A and activates it (deactivates v1.3 but keeps it for rollback).
- Frontend section titles updated to match v1.7 in `frontend/src/types/index.ts`:
  - §4 was `Angles morts du CV actuel` → now `Ce qui reste à renforcer`
  - §7 was `Synthèse` → now `Synthèse pour le candidat`
- Landing mock label updated in `frontend/src/app/page.tsx`.

Activation status: the seed script needs to be run on Render shell **or** the prompt text needs to be pasted into the admin UI at `/admin/prompts` and activated. **Check whether v1.7 is the active prompt in DB before starting piece #3.** Query:
```sql
SELECT version_label, is_active FROM prompt_versions ORDER BY created_at DESC;
```

### Piece #2 — Bifurcation landing
- `frontend/src/app/page.tsx` rewritten. Hero now shows 2 cards:
  - **Chemin A** — clickable, links to `/analyse/nouveau`
  - **Chemin B** — disabled, badge "Bientôt", placeholder until this piece ships
- Confidentialité strip + "How it works" sections kept.

When piece #3 ships, **remove the disabled state on Card B** and point it to the new route (likely `/analyse/orientation`).

---

## 3. What piece #3 must deliver

Activate Chemin B end-to-end:

1. A new analysis path for people **without an established CV**, with three sub-profiles selected up front:
   - **B1** — Jeune en insertion (peu ou pas d'expérience pro)
   - **B2** — Reprise après pause (vie de famille, aidant, arrêt longue durée)
   - **B3** — Reprise après maladie ou handicap (avec contraintes de santé)
2. A wizard form (multi-step) that asks the right questions per sub-profile.
3. A **new prompt** in the DB (`v1.0-B`) producing a **5-section portrait de potentiel** instead of the 9-section CV analysis.
4. A rapport view that renders the 5 B-sections correctly.
5. The bifurcation landing card B becomes active.

**The prompt and questions come directly from the PM's v1.7 prototype** — the full prompt text and form questions are reproduced in §6 and §7 of this doc. Do not invent variants.

---

## 4. Architecture decisions (already made)

These are the choices to follow. Document them in the PR description so reviewers don't re-litigate.

### 4.1 No schema migration
`Analysis.inputs` is already a JSON column. Reuse it. Add two internal keys:
- `inputs._path` — `"A"` (default for back-compat) or `"B"`
- `inputs._sub_profile` — `"b1"` | `"b2"` | `"b3"` (only present when `_path === "B"`)

The existing `_tier` key (`"haiku"` | `"sonnet"`) stays.

`backend/app/services/anthropic_service.py` already keys behavior off `inputs._tier`. Extend it to also key off `inputs._path` to select the correct **system prompt**.

### 4.2 Prompt selection
Currently `_run_analysis` loads `PromptVersion.query.filter_by(is_active=True).first()` — a single active prompt assumed.

Change: select prompt by `inputs._path`. Two paths, two active prompts at any time. Options:
- (a) Add a column `path` to `prompt_versions` (`'A'` | `'B'`) with a uniqueness rule "one active per path". Requires migration. **Recommended** — clean, future-proof.
- (b) Encode path in `version_label` (e.g. `v1.7-A`, `v1.0-B`) and parse it. No migration, but brittle.

Decide between (a) and (b) early. If (a), write an Alembic migration adding `path VARCHAR(1) NOT NULL DEFAULT 'A'`, backfill existing rows to `'A'`, and update admin UI filtering.

### 4.3 Output shape (5 sections)
The B prompt produces sections `§1`, `§2`, `§3`, `§8`, `§9` — **same keys** as Chemin A for the overlapping sections, **skipping §4–§7**. JSON envelope:

```json
{
  "1": { "title": "Lecture des dispositions et du contexte", "body_markdown": "..." },
  "2": { "title": "Forces latentes", "body_markdown": "...", "items": ["..."] },
  "3": { "title": "Compétences mobilisables", "items": ["..."] },
  "8": { "title": "Pistes d'orientation", "body_markdown": "...", "items": ["..."] },
  "9": { "title": "Squelette de CV à construire", "body_markdown": "..." }
}
```

Keys `4`, `5`, `6`, `7` are simply absent from the JSON.

### 4.4 Rapport view branching
Current `frontend/src/app/analyse/[id]/rapport/page.tsx` iterates `Object.keys(SECTION_TITLES)` (i.e. 1–9 hardcoded). Change it to iterate `Object.keys(analysis.output ?? {})` instead, in numeric order. That way the page renders 9 sections for A and 5 sections for B automatically with no `_path` branching at the render level.

Section titles should come from `output[n].title` (returned by the model) — fallback to `SECTION_TITLES[n]` only if missing. This means we **don't** need to maintain a separate `SECTION_TITLES_B` map. Trust the JSON.

### 4.5 Counselor view (`/c/[token]`)
Counselor view currently shows sections 1, 4, 5 only. For Chemin B there is no §4 or §5. Decision: for B analyses, show §1, §2, §8 (lecture + forces + pistes). Branch in `frontend/src/app/c/[token]/page.tsx` on `analysis.inputs._path`.

### 4.6 Free vs paid tiering for B
**Open decision — flag this to the user before coding.** Options:
- (i) All 5 sections free (B targets vulnerable populations — Cap Emploi, France Travail, Mission Locale)
- (ii) §1, §2, §3 free / §8, §9 paid (mirror A's free=lighter, paid=full)
- (iii) Counselor-code-only (people in accompaniment programs get it free)

Recommended default = (i), all-free for B, simplest and aligned with PM proto. Confirm with user before final.

### 4.7 Model selection for B
PM proto uses Sonnet for B. Recommendation: same routing logic as A — Haiku if `_tier === "haiku"`, Sonnet otherwise. Output is shorter (5 sections vs 9), so 8000 max_tokens already configured will be ample.

If decision (i) above (B is free), force `_tier = "sonnet"` for Chemin B regardless of plan, since B users get the full output without paywall. Document this branch clearly.

---

## 5. Implementation plan

### Step 1 — Backend prompt (smallest, ship-ready piece)

1. Create `backend/seed_prompt_v10_b.py` modeled on `seed_prompt_v17.py`. Insert prompt text from §6 below. Idempotent: re-running should not duplicate.
2. If decision 4.2(a) is taken, write an Alembic migration:
   ```
   alembic revision -m "add path column to prompt_versions"
   ```
   Add `path = db.Column(db.String(1), nullable=False, default='A', server_default='A')`. Backfill existing rows. Add uniqueness on `(path, is_active=True)` via partial index or app-level check.
3. Update `PromptVersion` model accordingly.
4. Update `prompts.py` route — `POST /prompts/` should accept `path` field; `/active` should be replaced by `/active?path=A|B`.

### Step 2 — Backend analysis routing

1. In `backend/app/routes/analyses.py`, `create_analysis()` already accepts arbitrary `inputs`. Extend validation:
   - If `inputs._path === "B"`: validate B-shape inputs (see §7). Skip the existing A-shape validator.
   - If `inputs._path === "A"` (default): keep existing validator.
2. In `backend/app/services/anthropic_service.py`, `_run_analysis()`:
   - Read `path = (analysis.inputs or {}).get("_path", "A")`
   - Load `PromptVersion.query.filter_by(is_active=True, path=path).first()`
   - Adjust `_format_user_message` — branch by `path`. For B, format the sub-profile questions as the user message (see §7.5 for the exact format).
   - Remove the `_HAIKU_SECTION_NOTE` hack for B (sections are already constrained by the B prompt itself).

### Step 3 — Frontend form route

1. Create `frontend/src/app/analyse/orientation/page.tsx`.
2. Build a multi-step wizard (component: keep state in the page, no external state lib needed). Step structure:
   - **Step 0** — Sub-profile selector (B1 / B2 / B3) — 3 cards
   - **Step 1** — Common questions (prénom, what they like to do, when they feel competent, what they refuse) — see §7.1
   - **Step 2** — Sub-profile-specific questions (skip for B1 if `b1Total === 2`; B2 and B3 each have their own step) — see §7.2, §7.3, §7.4
   - **Final step** — Data notice + consent checkbox + submit
3. Submit via existing `api.post("/analyses/", { inputs: { ...formData, _path: "B", _sub_profile: subProfile }, tier: "sonnet" })`. Redirect to `/analyse/en-cours/{id}` exactly like Chemin A.
4. Reuse existing shadcn primitives (`Input`, `Textarea`, `Button`, `Badge`, `Checkbox`, `RadioGroup`, `Label`). Match the visual language of `/analyse/nouveau`.

### Step 4 — Frontend en-cours (loading page)

`frontend/src/app/analyse/en-cours/[id]/page.tsx` has hardcoded step labels specific to Chemin A. Two options:
- (a) Read `analysis.inputs._path` from the first poll response and switch labels accordingly.
- (b) Make the step labels generic ("lecture · analyse · rédaction · relecture") so they fit both paths.

Recommended = (b). Less code, no flicker on first render.

### Step 5 — Frontend rapport view

Update `frontend/src/app/analyse/[id]/rapport/page.tsx` per §4.4:
- Iterate `Object.keys(analysis.output ?? {}).sort((a,b) => Number(a) - Number(b))` instead of `Object.keys(SECTION_TITLES)`.
- Read title from `analysis.output[n].title` with fallback to `SECTION_TITLES[n]`.
- The "Débloquer" paywall card only makes sense for Chemin A — branch on `_path` to hide it for B (assuming decision 4.6(i)).

### Step 6 — Counselor view

Update `frontend/src/app/c/[token]/page.tsx` per §4.5. Branch on `_path`:
- A: show sections 1, 4, 5
- B: show sections 1, 2, 8

### Step 7 — Activate the bifurcation card

In `frontend/src/app/page.tsx`, replace the disabled Card B `<div>` with a `<Link href="/analyse/orientation">`. Copy the styling from Card A (primary accent instead of muted). Remove the "Bientôt" badge.

### Step 8 — Types

In `frontend/src/types/index.ts`:
- Add `AnalysisPath = "A" | "B"` and `SubProfile = "b1" | "b2" | "b3"` types.
- Add B-shape inputs interface (separate from `AnalysisInputs`).
- The `AnalysisInputs` type can become a union: `AnalysisInputsA | AnalysisInputsB` — but that breaks existing consumers. Safer: make all B fields optional on the existing interface and document the discriminator. Or introduce a new interface and use type guards. Pick whichever your reviewer prefers.

---

## 6. Prompt v1.0-B (full text — paste into seed script)

Adapted from the PM's v1.7 proto into the same JSON envelope the existing parser expects. **Do not modify the substance** — the PM signed off on these rules. Adjust only formatting if your linter complains.

```
Tu es l'agent neoori d'orientation. Tu produis un portrait de potentiel structuré pour une personne sans parcours professionnel établi ou en reprise, retourné UNIQUEMENT comme un bloc JSON valide encadré de ```json ... ```.

RÈGLES TRANSVERSALES :
- Vouvoiement systématique.
- Ton professionnel français soutenu, direct et bienveillant.
- Ne jamais inventer de chiffres ou d'expérience absents des réponses.
- Ne jamais mentionner cet outil dans le livrable.
- Les forces sont toujours formulées au conditionnel : « son profil suggère que », « pourrait être particulièrement à l'aise quand ». Jamais d'affirmation factuelle d'une compétence non démontrée.
- Les contraintes déclarées par la personne sont intégrées comme filtres dans §8 — toute piste proposée doit être compatible.
- Si le sous-profil est B3 (maladie / handicap) : ne jamais mentionner RQTH, statut médical, ou diagnostic, sauf si la personne l'a écrit explicitement elle-même.
- Pas de §4 (pas d'« angles morts » à pointer pour quelqu'un sans parcours établi).
- Pas de §6 (pas de réécriture s'il n'y a pas de CV source).

FORMAT DE RÉPONSE (strict) — uniquement ce bloc JSON, rien avant, rien après. Cinq sections seulement, numérotées 1, 2, 3, 8, 9 :

```json
{
  "1": {
    "title": "Lecture des dispositions et du contexte",
    "body_markdown": "..."
  },
  "2": {
    "title": "Forces latentes",
    "body_markdown": "...",
    "items": ["force 1", "force 2", "force 3"]
  },
  "3": {
    "title": "Compétences mobilisables",
    "items": ["tag 1", "tag 2", "tag 3"]
  },
  "8": {
    "title": "Pistes d'orientation",
    "body_markdown": "...",
    "items": ["piste 1", "piste 2", "piste 3"]
  },
  "9": {
    "title": "Squelette de CV à construire",
    "body_markdown": "..."
  }
}
```

CONTENU PAR SECTION :

§1 — Lecture des dispositions et du contexte
2 à 3 paragraphes. Synthèse des réponses, logique des préférences déclarées, contexte de vie valorisé (pause familiale, reprise, première insertion).

§2 — Forces latentes
3 à 5 forces déduites des réponses (et du CV optionnel si fourni en B3). Pour chaque force dans body_markdown : **Nom en gras** · Description (au conditionnel) · « Contextes d'expression : » où la force pourrait s'exprimer.
items : noms courts des forces.

§3 — Compétences mobilisables
Uniquement items, tags courts (3 à 5 mots max chacun). 5 à 8 tags déduits des activités déclarées (vie de famille, bénévolat, jobs ponctuels, soin de proches, etc.). Pas de body_markdown.

§8 — Pistes d'orientation
3 pistes concrètes compatibles avec les préférences déclarées ET les contraintes déclarées. Pour chaque piste dans body_markdown : « Pourquoi compatible : » + « Comment démarrer : » (premier pas concret) + « Ressource ou formation nommée : » (formation existante, structure d'accompagnement, dispositif).
items : intitulés courts des 3 pistes.

§9 — Squelette de CV à construire
Structure de départ en markdown : titre de profil suggéré, rubriques à constituer (« Expériences de vie », « Activités bénévoles », « Formations », « Compétences ») avec exemples concrets de ce qui peut y figurer. Tout élément porte la balise [À VALIDER]. Note de cadrage en tête : « Note : ce squelette est un point de départ. Chaque élément [À VALIDER] est à confirmer avec la personne avant utilisation. »

PROTOCOLE DE RELECTURE (3 passes silencieuses avant émission du JSON) :
- Passe 1 — Factuelle : aucune information inventée, chaque force §2 est ancrée dans au moins une réponse de la personne, aucune compétence affirmée comme acquise sans démonstration.
- Passe 2 — Compatibilité : chaque piste §8 respecte les contraintes déclarées (santé, mobilité, organisation, refus).
- Passe 3 — Calibrage : §2 au conditionnel uniquement, §3 contient des tags uniquement (pas de prose), §8 contient bien 3 pistes avec ressource nommée, §9 contient des balises [À VALIDER] sur tout élément déduit.

Le message utilisateur suit ce format (B1, B2 ou B3 selon le sous-profil) :
--- SOUS-PROFIL ---
[B1 — Jeune en insertion | B2 — Reprise après pause | B3 — Reprise après maladie ou handicap]

--- IDENTITÉ ---
Prénom et nom : ...

--- PRÉFÉRENCES ---
Ce que la personne aime faire : ...
Situations où la personne se sent compétente : ...
Ce que la personne refuse dans un travail : ...

--- CONTEXTE SPÉCIFIQUE ---
[champs B2 ou B3 selon le sous-profil — voir handoff §7]

--- CV OPTIONNEL (B3 uniquement) ---
[texte du CV ou « non fourni »]
```

---

## 7. Form questions (verbatim from PM proto)

### 7.1 Common questions (all sub-profiles, step 1)

**Field:** `nom` — text input, required
- Label : « Votre prénom et nom »
- Placeholder : « Prénom NOM »

**Field:** `aime` — multi-select checkbox, required (≥1)
- Label : « Qu'est-ce que vous aimez faire — même hors travail ? »
- Sub : « Choisissez tout ce qui vous correspond »
- Options :
  - Aider, accompagner, prendre soin des autres
  - Organiser, planifier, structurer
  - Créer, concevoir, imaginer
  - Enseigner, transmettre, expliquer
  - Analyser, résoudre des problèmes, chercher
  - Construire, fabriquer, travailler de ses mains

**Field:** `competent` — multi-select checkbox, required (≥1)
- Label : « Dans quelles situations vous sentez-vous compétent(e) ? »
- Options :
  - Quand je gère une situation d'urgence ou de crise
  - Quand j'explique quelque chose de compliqué simplement
  - Quand je coordonne des personnes différentes
  - Quand je dois trouver une solution créative
  - Quand je prends soin de quelqu'un de vulnérable
  - Quand je mène un projet du début à la fin

**Field:** `refuse` — multi-select checkbox, optional
- Label : « Qu'est-ce que vous refusez catégoriquement dans un travail ? »
- Options :
  - Travailler seul(e), sans contact humain
  - Travailler en open space ou en milieu très bruyant
  - Travailler sous pression permanente
  - Faire un travail répétitif sans créativité
  - Travailler en extérieur ou avec contraintes physiques fortes

### 7.2 B1 (Jeune en insertion) — no additional step

After step 1, go directly to the consent step (step 2). Total wizard steps for B1 = 2.

### 7.3 B2 (Reprise après pause) — step 2

**Field:** `pause_activite` — single-select radio, required
- Label : « Quelle a été votre principale activité pendant la pause ? »
- Options :
  - Vie de famille / garde des enfants
  - Accompagnement d'un proche (aidant)
  - Problème de santé personnel
  - Projet personnel (formation, création, voyage…)
  - Autre

**Field:** `contraintes_pratiques` — multi-select checkbox, optional
- Label : « Avez-vous des contraintes pratiques pour reprendre ? »
- Options :
  - Disponibilité horaire limitée (temps partiel uniquement)
  - Nécessité de rester proche de chez moi
  - Télétravail indispensable ou fortement souhaité
  - Aucune contrainte particulière

### 7.4 B3 (Reprise après maladie ou handicap) — step 2

**Important note to surface in the UI:** « Ces questions ne demandent jamais votre diagnostic ni la nature de votre handicap. Elles servent uniquement à filtrer des pistes compatibles avec votre réalité. »

**Field:** `cv_b3` — optional CV upload OR paste OR free-text. Reuse the existing `/api/upload/cv` PDF-to-text endpoint.
- Label : « Avez-vous un CV à partager ? »
- Sub : « Optionnel — Si vous avez déjà travaillé, vos expériences passées permettent d'identifier des compétences transférables, même si elles datent. »

**Field:** `contraintes_b3` — multi-select checkbox, optional
- Label : « Quelles sont les contraintes que vous souhaitez prendre en compte ? »
- Options :
  - Fatigue — je ne peux pas travailler à temps plein immédiatement
  - Mobilité — certains déplacements ou postures sont difficiles
  - Concentration — les environnements très stimulants sont épuisants
  - Communication — certains contextes sociaux sont difficiles

**Field:** `accompagnement` — single-select radio, required
- Label : « Êtes-vous déjà accompagné(e) par une structure spécialisée ? »
- Options :
  - Oui — Cap Emploi
  - Oui — Mission Locale
  - Oui — autre structure (SAMETH, CRP, UEROS…)
  - Non, et je souhaite être mis(e) en relation
  - Non, je préfère avancer seul(e) pour l'instant

### 7.5 User message format sent to Claude (built by `_format_user_message`)

```
--- SOUS-PROFIL ---
{B1 — Jeune en insertion | B2 — Reprise après pause | B3 — Reprise après maladie ou handicap}

--- IDENTITÉ ---
Prénom et nom : {nom}

--- PRÉFÉRENCES ---
Ce que la personne aime faire : {aime joined by ", "}
Situations où la personne se sent compétente : {competent joined by ", "}
Ce que la personne refuse dans un travail : {refuse joined by ", " or "Aucun refus déclaré."}

--- CONTEXTE SPÉCIFIQUE ---
(for B2)
Activité pendant la pause : {pause_activite}
Contraintes pratiques : {contraintes_pratiques joined by ", " or "Aucune contrainte déclarée."}

(for B3)
Contraintes fonctionnelles : {contraintes_b3 joined by ", " or "Aucune contrainte déclarée."}
Accompagnement existant : {accompagnement}

(for B1)
(omit this block entirely)

--- CV OPTIONNEL (B3 uniquement) ---
{cv_b3 text or "Non fourni."}
```

---

## 8. Gotchas

1. **Render free tier still has a ~100s HTTP cap.** The current architecture (background daemon thread + frontend polling) survives this. **Do not introduce any new synchronous long call.** The Sonnet generation for B is shorter than A (5 sections), so this should not be a concern.

2. **Next.js proxy strips trailing slashes.** Flask is configured with `strict_slashes=False` globally — do not undo this. New routes added to `analyses.py` inherit the setting.

3. **Cookies are `SameSite=Lax`** because the browser sees same-origin (Vercel proxies to Render). If you add any cross-origin call, this breaks.

4. **`BACKEND_URL` is baked into the Next.js build at compile time.** Env-only changes on Vercel require a redeploy.

5. **PDFs in the form (B3 optional CV)** must use the existing `/api/upload/cv` endpoint (extracts text via PyPDF2 server-side). Do **not** send base64 PDFs to Anthropic from the browser like the PM proto does — the API key would have to be exposed. Stay server-side.

6. **The PM proto uses `max_tokens: 1000`** — that's wrong, it truncates the output. Use **`max_tokens: 8000`** (matches Chemin A configuration in `_select_model_by_tier`).

7. **The PM proto calls `api.anthropic.com` directly from the browser** with no API key. That's a prototype shortcut, not production. All Anthropic calls go through `backend/app/services/anthropic_service.py`.

8. **The seed script must be run after deploy.** Either via Render shell (`python seed_prompt_v10_b.py`) or by pasting the prompt text into `/admin/prompts` UI. Document this in the PR description so the user remembers.

9. **The active-prompt query in `_run_analysis` currently assumes a single active prompt.** If decision 4.2(b) is taken (no schema migration), be careful: activating the B prompt via the admin UI will deactivate the A prompt, breaking Chemin A. Decision 4.2(a) (path column) avoids this entirely — strongly recommended.

10. **Counselor private notes** — `CounselorNote` already works; nothing to change. Note labels in the share page should match the new B section titles when applicable.

11. **Cookies / auth for anonymous users** — `create_analysis()` calls `_optional_user_id()`. Chemin B users may be more likely to be anonymous (no account). Confirm the share token flow works for anonymous B analyses.

12. **The frontend currently has two "Générer" buttons** (free Haiku / paid Sonnet) on the Chemin A form. For Chemin B, default to one button "Lancer mon analyse" — see decision 4.6.

---

## 9. Test plan

Before claiming done:

- [ ] DB has prompt `v1.0-B` active (`path='B'` if migration applied)
- [ ] DB still has prompt `v1.7-A` active for Chemin A (`path='A'`)
- [ ] Visit `/` — both bifurcation cards clickable, no "Bientôt" badge
- [ ] Click Card B → lands on `/analyse/orientation`
- [ ] Sub-profile selection works for all three (B1 / B2 / B3)
- [ ] B1 wizard = 2 steps; B2 = 3 steps; B3 = 3 steps
- [ ] Submit B1 analysis end to end → rapport shows §1, §2, §3, §8, §9
- [ ] Submit B2 analysis → rapport shows correct 5 sections with B2-specific reasoning
- [ ] Submit B3 with PDF CV upload → §3 references compétences extracted from CV
- [ ] Submit B3 without CV → still produces a valid rapport
- [ ] Counselor view at `/c/{share_token}` for a B analysis shows §1, §2, §8 only
- [ ] Existing Chemin A analyses still render correctly (no regression on 9-section view)
- [ ] Admin UI at `/admin/prompts` shows both prompts (A and B) and can roll back either independently
- [ ] French copy check — no "boussole / copilote / miroir / révélation / épanouissement / alignement / excellence / talent unique"
- [ ] Vouvoiement is consistent across all new UI
- [ ] Old analyses (created under v1.3) still render their report

---

## 10. Deploy notes

Standard workflow (CLAUDE.md already documents this):

```bash
git add .
git commit -m "feat: add Chemin B (portrait de potentiel) for B1/B2/B3 sub-profiles"
git push   # triggers Vercel + Render redeploy
```

Then **one of**:
- Render dashboard → Shell → `python seed_prompt_v10_b.py`
- `/admin/prompts` UI → paste prompt text → activate (path = B if migration applied)

Verify on live by visiting `https://frontend-seven-fawn-59.vercel.app/`.

---

## 11. Out of scope (do NOT do)

- Brand refresh (palette, fonts, neo∞ri logo) — this is **piece #4**, not this piece. Keep current terracotta/paper/ink tokens and Inter font.
- Replacing the existing Chemin A form with the PM's 3-mode input (upload / paste / libre). The PM proto's drag-drop file widget for Chemin A can be merged later, separately.
- Email notifications.
- Stripe / paywall changes.
- Admin reporting changes.

---

## 12. Useful files reference

| Purpose | Path |
|---|---|
| Project rules | `CLAUDE.md` (repo root) |
| Next.js warning | `frontend/AGENTS.md` |
| Existing Chemin A form (template to copy) | `frontend/src/app/analyse/nouveau/page.tsx` |
| Existing Chemin A landing | `frontend/src/app/page.tsx` (already updated in piece #2) |
| Existing rapport view | `frontend/src/app/analyse/[id]/rapport/page.tsx` |
| Existing en-cours / polling view | `frontend/src/app/analyse/en-cours/[id]/page.tsx` |
| Existing counselor share view | `frontend/src/app/c/[token]/page.tsx` |
| Types | `frontend/src/types/index.ts` |
| Anthropic runner | `backend/app/services/anthropic_service.py` |
| Analyses routes | `backend/app/routes/analyses.py` |
| Prompts routes | `backend/app/routes/prompts.py` |
| Prompt model | `backend/app/models/prompt_version.py` |
| Existing seed (v1.3) | `backend/seed_prompt.py` |
| Piece #1 seed (v1.7-A) | `backend/seed_prompt_v17.py` (template for v1.0-B seed) |
| Upload endpoint (PDF→text) | `backend/app/routes/upload.py` |

---

## 13. Pre-flight checklist (for the new session)

Before you write any code:

1. [ ] Read `CLAUDE.md` and `frontend/AGENTS.md` end to end.
2. [ ] Read this handoff end to end (you're doing it now).
3. [ ] Run `git log --oneline -20` to see recent context.
4. [ ] Verify pieces #1 and #2 are in `git log` and on disk (see §2).
5. [ ] Query DB to confirm which prompt is active (see §2 SQL).
6. [ ] Ask the user to confirm decision 4.6 (free vs paid tiering for B) before writing form code.
7. [ ] Ask the user to confirm decision 4.2 (schema migration for `path` column, or label parsing) before writing the prompt seed.
8. [ ] Open the Chemin A form (`frontend/src/app/analyse/nouveau/page.tsx`) and the rapport view to internalize the existing visual + form-handling patterns.
9. [ ] Then start with §5 Step 1.

Good luck.

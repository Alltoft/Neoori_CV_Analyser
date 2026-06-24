# Handoff — neoori · Module Analyse CV (bêta)

## Overview

This handoff covers the **first of two core modules** of the neoori product: the **CV Analyzer**. A candidate uploads their CV, fills 8 contextual fields, and an AI model returns a structured strategic analysis. The same analysis object produces two exports: one for the candidate, one for their counselor (Cap Emploi / Mission Locale / France Travail / CEP).

The second module (Portrait, a guided exploration of aspirations & values) is out of scope for this implementation — but the data model and module boundaries should leave room for it.

App language: **French**. Audience: French job-seekers and the public-employment professionals who accompany them.

## About the design files

The files in `wireframes/` are **design references created in HTML** — sketchy, low-fidelity prototypes that show intended structure, flow, content hierarchy, and behaviour. They are **not production code to copy**. Your job is to **recreate them in your target stack** (React/Next.js, Vue/Nuxt, SvelteKit — whatever you choose) using that stack's conventions, component library, and design system.

If no codebase exists yet, pick a stack and start clean. The HTML prototypes are a thinking aid, not a starting point.

## Fidelity

**Low-fidelity wireframes.** Layout, hierarchy, and content are decided. Final visual system (typography, color, spacing scale, components) is **not** — neoori does not have a finalised design system yet. Build using a sober, professional default (Inter or similar + a single accent color) and treat the wireframe annotations ("post-its") as designer intent, not literal copy.

The wireframes are intentionally hand-drawn so nobody mistakes them for a finished UI.

## Spec & source of truth

`spec/Neoori_Reponses_Questions_Developpeur_Mai2026.pdf` — official product cadrage doc. **When the wireframes and the spec disagree, the spec wins.** Especially:

- The 8 form fields (names, types, required/optional) are fixed in the spec.
- The 11 tone rules (vouvoiement, no jargon, no clichés, no marketing language…) are non-negotiable and live **inside the system prompt v1.3**, not in your code.
- The Anthropic model id (`claude-sonnet-4-20250514`), `max_tokens >= 4000`, and the `user`-message composition format come from the spec.

## Scope of this implementation (bêta)

| Screen / area | Status |
|---|---|
| Landing (public) | Build |
| New analysis — 8-field form, single page (variant A) | Build |
| Generation/loading state | Build |
| Deliverable — A4 report layout (variant C), candidate version, 9 sections | Build |
| Deliverable — counselor export (sections 1, 4, 5 only) | Build — same analysis object, alternate export |
| Paywall (free → paid) | Build |
| User space — history of past analyses | Build |
| Admin dashboard — prompt editor + analytics + logs | Build |
| Portrait module | Out of scope |
| CV-per-job adaptation | Out of scope |
| Guided application / personal assistant | Out of scope |

---

## 1. Landing

**Purpose** — public entry point. Sells the analyzer in three beats and pushes to the form.

**Layout** — single page, max-width container ~1100px, comfortable vertical rhythm.

**Sections (top to bottom)** :
1. Header — `neoori` wordmark left; nav links right: `Le module`, `Conseillers`, `Tarifs`, `Se connecter`.
2. Hero — large heading on the left ("Un CV lu autrement. Pour les parcours qu'on ne sait pas lire."), short subline, primary CTA `analyser mon CV →`, secondary `voir un exemple`. On the right, a stacked illustration of the deliverable (candidate report on top, counselor report behind) — replace with a styled component or static image.
3. 3-step "how it works" row (`01 · Vous racontez votre cible`, `02 · neoori traduit`, `03 · 3 lectures, 1 document`).
4. Trust/footer band (later).

**Reference** — `wireframes/frames-entry.jsx` → `FrameLanding`.

---

## 2. New analysis — the form (variant A, single page)

**Purpose** — collect the 8 mandatory inputs that feed the AI.

**Layout** — single page, vertically scrolling, ~720px content column. Header: `Nouvelle analyse · 8 champs · ~2 min`.

**The 8 fields (all required; spec, page 1):**

| # | Field | Type | Notes |
|---|---|---|---|
| 1 | CV | PDF upload **or** pasted plain text | Either input fulfils the requirement. PDF max 10 MB. Drag & drop + click-to-pick. |
| 2 | Cible visée | Long text | Job offer, fiche métier, or training program description. Min ~50 chars. |
| 3 | Prénom | Short text | |
| 4 | Tranche d'âge | Select | Brackets: `< 25`, `25–34`, `35–44`, `45–54`, `55+`. |
| 5 | Localisation | Short text | City or region. |
| 6 | Situation actuelle | Select | `en poste`, `en recherche`, `en formation`, `en pause`. |
| 7 | Type de mobilité | Select / chip | `évolution`, `reconversion proche`, `reconversion forte`, `première insertion`, `retour à l'emploi`. |
| 8 | Notes spécifiques | Long text (optional in feel, but the spec lists it as part of the required 8 — keep it required-but-can-be-empty, accept a blank string) | RQTH, aidant, primo-arrivant, handicap, contraintes. |

**Card grouping (visual only, not data):**
- Card 1 — `① votre CV` — split layout: drop zone on the left, paste textarea on the right.
- Card 2 — `② cible visée` — full-width textarea.
- Card 3 — `③ qui êtes-vous` — 2-col grid: prénom, tranche d'âge, localisation, situation actuelle.
- Card 4 — `④ type de mobilité` (chips) + `⑤ notes` (textarea).

**Footer bar** — left: `données stockées chiffrées · supprimables à tout moment`. Right: `enregistrer brouillon` (secondary) + `lancer l'analyse →` (primary accent).

**Validation**
- All required fields filled.
- CV input: either `pdf_file` non-null OR `cv_text.length > 200`.
- `cible_visee.length > 50`.

**Reference** — `wireframes/frames-entry.jsx` → `FrameFormA`.

---

## 3. Generation / loading state

**Purpose** — show the user the AI is working without an anonymous spinner.

**Layout** — centered column, ~520px wide.
- Top tag: `EN COURS · ~40 SEC`.
- Big handwritten-feel heading: `neoori vous lit.`
- Sub-line: `prompt système v1.3 · claude-sonnet-4 · max 4 000 tokens` (debug info; can be subtle in prod).
- Step-by-step checklist of 6 stages with state `done | active | wait | wait-locked`:
  1. `lecture du CV`
  2. `cadrage sectoriel · cible identifiée`
  3. `lecture stratégique du parcours`
  4. `forces · compétences transférables`
  5. `points à renforcer · préconisations`
  6. `proposition de CV retravaillé` (locked badge for free plan)
- Progress bar (% of estimated total).
- Sub-line: `vous pouvez fermer cet onglet — on vous prévient par e-mail`.

**Behaviour**
- The API call is a single `messages.create` to Claude. The 6 "steps" are a **UX simulation** keyed on elapsed time (e.g. 7s, 13s, 22s, 30s, 38s, 45s) — they are not real per-step boundaries. Confirm with product.
- If the user closes the tab, an e-mail with the result link must be sent on completion.
- On timeout (>120s) or error → friendly error screen with retry.

**Reference** — `wireframes/frames-entry.jsx` → `FrameLoading`.

---

## 4. The deliverable — variant C (A4 report)

**Purpose** — the analysis itself, rendered as a document the user can read, print, share with a RH, or send to a counselor.

**Layout** — A4-feel page floating on a warm-grey background.
- Page width ~560px content, padding 46/54px.
- Top utility bar (outside the page): tabs `vue rapport | vue navigable | vue conseiller`.
- Page header — bordered: `NEOORI · ANALYSE DE CV` small caps left, candidate name and cible right (or vice versa). neoori wordmark top-right.
- Body — sections numbered with stamp-style `§ 1` to `§ 9` badges.
- Footer of each page — left: `neoori · v1.3 · confidentiel`. Right: page count `1 / 6`.

**The 9 sections (output structure of the AI):**

| § | Title | Notes |
|---|---|---|
| 1 | Lecture stratégique du parcours | Free plan ✓ |
| 2 | Forces du profil pour la cible | Free plan ✓. Format: each force = **fact + condition of expression** (spec rule — never a quality without its condition). |
| 3 | Compétences transférables | Free plan ✓. Renders as a tag cloud. |
| 4 | Ce qui reste à renforcer | Free plan ✓ |
| 5 | Préconisations terrain (réseau, formation, portfolio, CEP) | **Paid only** |
| 6 | Exemple de réécriture | Paid only |
| 7 | Synthèse | Paid only |
| 8 | Pistes d'évolution (3 pistes au-delà de la cible) | Paid only |
| 9 | Proposition de CV retravaillé | Paid only |

**Print** — `@media print` must render the report cleanly, one logical section per page-break-after where needed, hide all chrome (top bar, tabs, paywall).

**Actions toolbar** (sticky or top-right): `↓ PDF`, `↗ partager`, `version conseiller` toggle.

**Reference** — `wireframes/frames-deliverable.jsx` → `FrameDeliverableC` (kept format), with the section list also visible in `FrameDeliverableA` (for content/copy reference only).

---

## 5. Counselor export (same analysis, different view)

**Purpose** — a counselor at Cap Emploi / Mission Locale / France Travail / CEP receives a link to a 5-minute synthesis to prepare a 1:1 with the candidate.

**Critical architecture rule (spec, page 3)** — *"deux modes d'export à partir du même objet d'analyse, sans régénération."* The analysis is generated once and stored. Two views (`audience=candidat` and `audience=conseiller`) render from the same data.

**Layout** — same A4 report shell as the candidate view, but:
- Header badge `VERSION CONSEILLER` (accent color).
- "Key facts" strip at the top — 4 cells: `Cible visée`, `Mobilité`, `Posture actuelle`, `Points sensibles`.
- Only sections **§ 1, § 4, § 5** are rendered. Other sections are not just hidden — they should not appear in the table of contents either.
- Bottom of the report: a **private notes field** (free text, saved on the counselor's account, **not shared with the candidate**).

**Sharing model**
- Each analysis has a public-link token (e.g. `neoori.fr/c/<token>`) that opens the counselor view.
- A counselor must be authenticated to write into the notes field; an unauthenticated visitor with the link only reads the synthesis.

**Reference** — `wireframes/frames-deliverable.jsx` → `FrameCounselor`.

---

## 6. Paywall — free → paid

**Purpose** — convert users who hit the free limit.

**Trigger** — anywhere the user tries to access sections 5–9 in the free plan, or clicks the explicit CTA at the bottom of the free deliverable.

**Layout** — two cards side by side.
- Left card · **Gratuit · 0 €** — checked items for §§ 1–4, strikethrough items for §§ 5–9.
- Right card (accent background) · **Complet · 9 € · une fois · sans abonnement** — all 9 sections checked. Primary CTA `débloquer pour 9 € →`. Sub-line: `code conseiller — gratuit pour les bénéficiaires Cap Emploi / France Travail`.
- Below the cards: a thin row with an input for a counselor-issued code.

**Design intent** — do **not** aggressively blur the free sections in the deliverable. The 4 free sections must be genuinely useful on their own; paying = going further, not unlocking the basics.

**Reference** — `wireframes/frames-deliverable.jsx` → `FramePaywall`.

---

## 7. User space (history)

**Purpose** — the candidate's home screen after they have at least one analysis.

**Layout** — header (`Mon espace` + CTA `+ nouvelle analyse`), grid of analysis cards, two-card strip at the bottom (share-with-counselor link, remaining credits).

**Each analysis card shows** : date, title (= cible visée), state (`complète` / `gratuite` / `brouillon`), plan (`payant` / `gratuit`), section count, mini preview, action row (`ouvrir`, `↓` download, `↗` share, kebab).

**Empty / first-time state** — replace the grid with a hero card pushing to "Nouvelle analyse".

**Reference** — `wireframes/frames-admin.jsx` → `FrameUserSpace`.

---

## 8. Admin dashboard

**Purpose** — internal tool. Required for bêta because the system prompt evolves often (v1.0 → v1.3 in 6 weeks).

**Top nav (admin context, not the public app):** `vue d'ensemble`, `prompts`, `analyses`, `utilisateurs`, `conseillers`, `coûts API`.

**Overview tab — what to show:**

1. KPI strip (5 cards): `analyses générées` (with weekly delta), `taux de succès` (with error/timeout count), `tokens consommés` (with € cost estimate), `conversion → payant` (%), `prompt actif` (version + age).
2. **Prompt editor** (left, big) :
   - Version pills (`v1.0` `v1.1` `v1.2` `v1.3 ACTIVE`).
   - Author & date of active version.
   - Multiline code editor (monospace) showing the prompt text.
   - Buttons: `éditer`, `comparer à v1.2`, `rollback v1.2`, `publier nouvelle version`.
   - Footer line: `traçabilité B2G : chaque analyse stocke la version utilisée`.
3. **Recent analyses log** (right) — table: time, name, target role, status (`succès` / `erreur` / `timeout`), prompt version used, audience requested. Read-only — no edit.
4. Sparkline strip — 3 mini-charts (analyses last 30d, tokens last 30d, plan split).

**Hard requirements (from spec)**
- Prompt must be editable in DB, never hardcoded.
- Every analysis row stores `prompt_version_used` for traceability (B2G context, future certification need).
- Versions: full history, with author + timestamp + ability to rollback.

**Reference** — `wireframes/frames-admin.jsx` → `FrameAdmin`.

---

## Data model (suggested)

```
User
  id, email, role: 'candidate' | 'counselor' | 'admin'
  plan: 'free' | 'paid'
  credits_remaining
  created_at

Analysis
  id
  user_id
  prompt_version_id          // FK → PromptVersion.id (traceability!)
  status: 'queued' | 'running' | 'success' | 'error' | 'timeout'
  inputs: {                  // the 8 fields, structured
    cv_text, cv_pdf_url, cible, prenom, age_bracket,
    location, situation, mobility, notes
  }
  output: {                  // structured AI response — see "Output schema" below
    sections: { '1': {...}, '2': {...}, ..., '9': {...} }
    sector_framing: 'tech' | 'ess' | 'public' | ...
  }
  tokens_in, tokens_out
  created_at, completed_at
  share_token                // for counselor link

CounselorNote
  id, analysis_id, counselor_id, body, updated_at

PromptVersion
  id, version_label ('v1.3'), system_prompt_text,
  author_id, created_at, is_active
```

## Output schema

The system prompt v1.3 is responsible for returning a structured response. Confirm with product the exact JSON shape — assume each section comes back as `{ title, body_markdown, items: [...] }`. Section 2 (forces) specifically returns items of shape `{ trait, condition_of_expression, fact, target_relevance }`. Section 3 returns a flat array of strings (tags).

## AI call

```
POST https://api.anthropic.com/v1/messages
{
  "model": "claude-sonnet-4-20250514",
  "max_tokens": 4000,
  "system": <PromptVersion.system_prompt_text>,   // never hardcoded
  "messages": [{
    "role": "user",
    "content": <concatenation of the 8 input fields in the format
                defined at the end of the prompt v1.3 — see spec>
  }]
}
```

- Anthropic key in env var `ANTHROPIC_API_KEY`.
- Stream the response; surface partial content if helpful for the loading screen.
- Persist the raw response alongside the parsed `output`.

## Tone rules (spec, page 2)

These live **in the prompt**, not in your code. But the front-end should not contradict them either — no boussole/copilote/miroir copy, no "vous vous démarquez", no marketing speak in your own UI strings.

## Design tokens (starting point — not final)

```
--accent       #c96442   (terracotta — placeholder; final color TBD)
--ink          #1d1a17
--ink-2        rgba(29,26,23,0.55)
--ink-3        rgba(29,26,23,0.32)
--paper        #faf7f0
--paper-2      #f3eee2

--radius-sm    4px
--radius-md    8px
--radius-lg    12px

--font-sans    Inter, system-ui, sans-serif    // production
--font-mono    'JetBrains Mono', monospace
```

Do **not** use the handwritten fonts (Caveat, Patrick Hand, Architects Daughter) from the wireframes — those are a sketching device.

## Files in this bundle

```
README.md                                              ← this file
spec/Neoori_Reponses_Questions_Developpeur_Mai2026.pdf ← official spec, source of truth
wireframes/index.html                                  ← entry, open in browser to navigate the canvas
wireframes/sketch.jsx                                  ← drawing primitives (reference only)
wireframes/frames-entry.jsx                            ← landing, form A/B/C/D, loading
wireframes/frames-deliverable.jsx                      ← deliverable A/B/C, counselor, paywall
wireframes/frames-admin.jsx                            ← admin dashboard, user space
wireframes/design-canvas.jsx                           ← canvas tooling
wireframes/tweaks-panel.jsx                            ← canvas tooling
```

## Selected directions (decided with the designer)

- **Form** — variant **A · single page** (`FrameFormA`).
- **Deliverable** — variant **C · A4 report** (`FrameDeliverableC`). Counselor view (`FrameCounselor`) uses the same shell.
- All other variants in the wireframes are explorations only; ignore them for build.

## Open questions for product before you start

1. Pricing — confirm the 9 € one-shot price and the counselor-code flow (who issues, how validated, billing model with public-employment partners).
2. Sharing — counselor link: time-limited? Single-use? Auth required to read?
3. Email delivery — confirm SMTP / provider (Postmark / Resend / SES) and template language (FR).
4. PDF generation — server-side (Puppeteer / wkhtmltopdf) or client-side (browser print)? The A4-report layout was designed with `@media print` in mind.
5. RGPD — retention, "right to be forgotten" flow for analyses, anonymisation of admin log views.
6. Sectorial framing — should the detected sector (8 options from spec) be visible to the user, or kept internal?

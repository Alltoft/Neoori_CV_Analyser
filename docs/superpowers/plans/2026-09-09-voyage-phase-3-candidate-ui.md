# Le voyage — Phase 3 · Candidate UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship everything the candidate touches in le voyage — the hub at `/voyage`, the session player, the validated portrait page, and the four entry points that lead to them — against the API phases 1–2 already expose.

**Architecture:** Four Next.js client pages (`/voyage`, `/voyage/session/[n]`, `/voyage/portrait`, plus edits to four existing pages) sit on top of one typed API module (`frontend/src/lib/voyage.ts`) and one type module (`frontend/src/types/voyage.ts`) that mirrors the backend contract key for key. Six presentational components in `frontend/src/components/voyage/` carry the repeated shapes — the six session stamps, one scene, one option, one checklist row, the exit ticket, the S0 phrase — and hold no fetching logic of their own. Every French word of session and portrait content arrives from `GET /api/voyage/bank` and `GET /api/voyage/portrait`; the only French this phase writes is app chrome.

**Tech Stack:** Next.js 16 App Router · React 19 · TypeScript (strict) · Tailwind v4 (CSS-first, no `tailwind.config`) · shadcn/ui in `src/components/ui` · base-ui primitives · lucide-react · `frontend/src/lib/api.ts` (fetch wrapper, cookie auth). No frontend test runner: verification is `npm run lint` + `npm run build` + manual rows in `TEST-PLAN.md`.

**Spec:** docs/superpowers/specs/2026-09-09-voyage-design.md
**Contracts:** docs/superpowers/plans/2026-09-09-voyage-contracts.md

## Global Constraints

- App UI strings are **French**. Code comments, docstrings and commit messages are **English** (`CLAUDE.md` § Language rule).
- Copy ban list — never in user-facing French **chrome** (hub, buttons, cards, nav, errors, landing, `/espace`): `boussole`, `copilote`, `miroir`, `révélation`, `épanouissement`, `alignement`, `excellence`, `talent unique`, `vous vous démarquez`.
- The ban does **not** reach the cahier text reproduced verbatim inside sessions and the portrait (spec decision 15) — that text arrives from the API and is rendered as received, including session 4's own title « Le cadre qui te permet de te révéler ».
- Tone split: session and portrait content is the cahier **verbatim, tutoiement**. Everything around it — buttons, cards, nav, errors, empty states — is **vouvoiement**, sober, factual.
- The model-facing label « Phrase révélée » (contracts § H) is **forbidden in the UI**. The hub labels the S0 sentence « Votre phrase » (contracts line 1619).
- **The candidate never sees a score, a trait name, or a framework name** (spec decision 7). Nothing in this phase renders `synthesis`, axes, RIASEC, Big Five, SDT, Schwartz, `plain`, or any numeric score. The only two things the candidate sees are the S0 phrase and the six portrait sections.
- **Never required** (spec decision 11). Every parcours runs identically with no voyage. No page in this phase may block, gate or nag an analysis flow; the voyage is always an offer, never a prerequisite. The hub says so in words.
- **Next.js caveat** (`frontend/AGENTS.md`): "This is NOT the Next.js you know — APIs, conventions and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code." Every task that touches a Next.js API begins with a read step naming the exact local doc.
- Backend tests run from `/Users/imran/Downloads/design_handoff_cv_analyzer/backend` with `pytest` (the repo venv is `backend/venv`; `./venv/bin/python -m pytest` works when the venv is not on PATH). Baseline before phases 0–2: **145 passed**. Fixtures `app`, `client`, `admin_headers` live in `backend/tests/conftest.py`.
- Alembic statuses are `String(16)` strings, never native enums; current head before the voyage migrations is `b8c9d0e1f2a3`. **This phase adds no migration and touches no Python** — it is listed here because Task 1 makes `backend/tests/test_voyage_parity.py` go green and Task 10 runs the whole suite.
- Prompts live in the DB (`PromptVersion`), never in code; structure comes from a JSON-schema `output_config`. Not touched by this phase.
- Never hold a DB connection across an Anthropic stream. Not touched by this phase.
- French route segments, English identifiers (contracts § J): routes `/voyage`, `/voyage/session/[n]`, `/voyage/portrait`; components `SessionProgress`, `SceneCard`, `OptionCard`, `ChecklistRow`, `BilletForm`, `MicroReveal`; helpers `sessionLock`, `missingItems`.
- Commit prefixes: `feat(voyage):`, `fix(voyage):`, `refactor(voyage):`, `chore(voyage):`, `docs(voyage):` — Conventional Commits, English subject, lowercase, no trailing period.
- `git push` on branch `initial` deploys. Every commit must leave `npm run build` passing and `pytest` green.

### What this phase depends on and does not build

Phase 3 consumes phases 1 and 2 and adds nothing to them. It must land **after** them.

| Consumed | Owner | Contract |
|---|---|---|
| `GET /api/voyage/bank` → `{bank: {scoring_version, sessions[]}}` | Phase 1 | contracts § E1 |
| `GET /api/voyage` → `{voyage: <to_dict()> \| null}` | Phase 1 | contracts § E2, § C.5 |
| `POST /api/voyage` `{consent, age_attested}` → `201 {voyage}` | Phase 1 | contracts § E3 |
| `GET /api/voyage/responses` → `{responses: {answers, billets}}` | Phase 1 | contracts § E4 |
| `PUT /api/voyage/responses` `{answers?, billets?}` → `{responses}` (full merged set) | Phase 1 | contracts § E5 |
| `POST /api/voyage/sessions/<n>/complete` → `{voyage}`; `400 {errors: [sentence, ...missing ids]}` | Phase 1 | contracts § E6 |
| `POST /api/voyage/unlock` `{code}` → `{voyage}` | Phase 1 | contracts § E7 |
| `GET /api/voyage/portrait` → `{portrait: {sections, validated_at}}`; `409 {error, status}` | Phase 1 | contracts § E8 |
| `DELETE /api/voyage` → `{message}` | Phase 1 | contracts § E9 |
| `session_lock()` and its three strings | Phase 1 | contracts § C.6 |
| micro + portrait generation (what the hub polls for) | Phase 2 | contracts § G |

Not in this phase: `/voyage/c/[token]` and `SynthesisSheet` / `RiasecBars` (phase 4); `_merge_profile()` injection and `Analysis.voyage_id` (phase 5); `CLAUDE.md` (phase 5).

### Ordering note for the parity test

`backend/tests/test_voyage_parity.py` (contracts § 0, owned by phase 0/1) reads `frontend/src/types/voyage.ts` **as text** and asserts the three lock strings and `PORTRAIT_SECTIONS` match Python — the same technique as the existing `backend/tests/test_conditions_parity.py:26-34`. That file cannot pass until Task 1 of this phase creates the TypeScript. Either land phases 1 and 3 in the same push, or accept that `test_voyage_parity.py` is the one red test between them. Task 1 turns it green and is the only real red→green cycle this phase has.

### Colour — why the voyage takes peach-on-navy

The requirement (spec § Frontend): the voyage must read as a **fourth scenario**, not a fourth parcours, and the accent must come from the charter tokens already declared in `frontend/src/app/globals.css:53-102`.

The three parcours already own the charter's three full-weight hues, and the colour is load-bearing wayfinding that survives into their form pages (`frontend/src/app/page.tsx:105-134`, `frontend/src/app/analyse/depart/page.tsx:100`):

| token | value | owner |
|---|---|---|
| `--orange` | `#ea5624` | parcours 1 |
| `--navy` | `#1c3561` | parcours 2 |
| `--teal` | `#2e8b6e` | parcours 3 |

What is left cannot carry a fourth white-card accent bar. `--navy-500` (`#2a4f91`) sits at **1.51:1** against `--navy` — on a 6 px rule the two read as one blue, so it would be mistaken for parcours 2. `--peach` (`#f7b394`) is a tint of the same hue family as `--orange` (2.02:1 apart) and only **1.78:1** on white, so on a white card it reads as parcours 1's little sibling and fails text contrast.

**Pick: `--peach` on a `--navy` field.** The voyage does not take a fourth hue on the same white card — it takes the charter's *inverted* surface. `--peach` on `--navy` measures **6.81:1** (AA at any size), and that pair is already a shipped charter idiom: the report header subtitle (`frontend/src/app/analyse/[id]/rapport/page.tsx:127`, `text-peach` on `bg-navy`) and the landing report preview (`frontend/src/app/page.tsx:35`). So:

- **surface** `bg-navy` (a full-width inverted card where the parcours cards are white thirds — legible before any hue is read, which is the actual wayfinding requirement),
- **accent** `text-peach` / `.voyage-rule` (`background: var(--peach)`, the sibling of `.report-rule`),
- **marks** `bg-white/10` chips, white body text at `text-white/80`.

No new colour value is introduced. `.voyage-rule` is the one new CSS class, added beside `.report-rule` in `globals.css`.

---

## File Structure

| File | Action | The one responsibility |
|---|---|---|
| `frontend/src/types/voyage.ts` | create | The API's shapes in TypeScript, the three lock strings, `PORTRAIT_SECTIONS`, and `sessionLock()` — the client mirror of the server gate |
| `frontend/src/lib/voyage.ts` | create | Nine typed wrappers over `/api/voyage/*` plus `missingItems()`; the only module that knows an endpoint path |
| `frontend/src/lib/api.ts` | modify:5-9, 35-44 | `ApiError` carries the response body, and an `{errors: [...]}` body surfaces its first string as the message |
| `frontend/src/proxy.ts` | modify:5 | `/voyage` joins `PROTECTED` |
| `frontend/src/app/globals.css` | modify:234-238 | `.voyage-rule` — the voyage's peach accent rule |
| `frontend/src/components/voyage/SessionProgress.tsx` | create | The six session rows: stamp, cahier title, and either a way in or the reason there is none |
| `frontend/src/components/voyage/MicroReveal.tsx` | create | The S0 sentence and its generating / error states |
| `frontend/src/app/voyage/page.tsx` | create | The hub: consent + age gate, progress, per-state CTA, phrase polling, code entry, portrait link, erasure |
| `frontend/src/components/voyage/ChecklistRow.tsx` | create | One S0 affirmation with its ✓ / ✗ pair |
| `frontend/src/components/voyage/OptionCard.tsx` | create | One lettered option of one scene |
| `frontend/src/components/voyage/SceneCard.tsx` | create | One scene screen: title, narrative, question, options |
| `frontend/src/components/voyage/BilletForm.tsx` | create | The exit ticket's optional free-text fields |
| `frontend/src/app/voyage/session/[n]/page.tsx` | create | The player: resume, one screen per scene, save-on-Suivant, billet, Terminer |
| `frontend/src/app/voyage/portrait/page.tsx` | create | The validated portrait on `.report-shell`, printable |
| `frontend/src/components/layout/AppBar.tsx` | modify:11, 45-48 | « Mon voyage » in the account dropdown |
| `frontend/src/app/analyse/page.tsx` | modify:1-6, 57-59 | The voyage card above the three parcours cards |
| `frontend/src/app/espace/page.tsx` | modify:3-20, 27-52, 78-79 | The voyage status strip at the top of the dashboard |
| `frontend/src/app/page.tsx` | modify:135, 231-233 | The landing voyage section above the three scenario cards |
| `TEST-PLAN.md` | modify:211-212 | « § 12 · Le voyage » — the PM-facing manual pass |

---

### Task 1: Types, API wrappers, error bodies, proxy, accent

**Files:**
- Create: `frontend/src/types/voyage.ts`
- Create: `frontend/src/lib/voyage.ts`
- Modify: `frontend/src/lib/api.ts:5-9` and `frontend/src/lib/api.ts:35-44`
- Modify: `frontend/src/proxy.ts:5`
- Modify: `frontend/src/app/globals.css:234-238`
- Test: `backend/tests/test_voyage_parity.py` (owned by phase 0/1 — this task is what makes it pass)

**Interfaces:**
- Consumes: `GET /api/voyage/bank`, `GET|POST|DELETE /api/voyage`, `GET|PUT /api/voyage/responses`, `POST /api/voyage/sessions/<n>/complete`, `POST /api/voyage/unlock`, `GET /api/voyage/portrait` (contracts § E1–E9); `models.voyage.LOCK_CODE|LOCK_PROFILE|LOCK_ORDER` and `session_lock()` (contracts § C.6); `generation.PORTRAIT_TITLES` (contracts § G.1).
- Produces:
  - Types `VoyageStatus`, `MicroStatus`, `PortraitStatus`, `SessionId`, `SessionKind`, `PortraitKey`, `BankBilletField`, `BankChecklistItem`, `BankOption`, `BankScene`, `BankItem`, `BankSession`, `Bank`, `BankResponse`, `Voyage`, `VoyageResponse`, `VoyageAnswer`, `VoyageResponses`, `ResponsesResponse`, `PortraitSections`, `CandidatePortrait`, `CandidatePortraitResponse`, `CounselorPortrait`, `CounselorPortraitResponse`, `AxisScore`, `AxisTension`, `AxisTop`, `RiasecTop`, `S0Score`, `RiasecScore`, `S2Score`, `S3Score`, `S4Score`, `S5Score`, `VoyageSynthesis`, `CounselorVoyage`, `CounselorVoyageResponse`, `VoyageNote`, `VoyageNoteResponse`
  - `isScene(item: BankItem): item is BankScene`
  - `PORTRAIT_SECTIONS: { key: PortraitKey; title: string }[]`
  - `LOCK_CODE`, `LOCK_PROFILE`, `LOCK_ORDER: string`
  - `sessionLock(voyage: Voyage | null, profile: { prenom?: string | null; tranche_age?: string | null } | null, n: SessionId): string | null`
  - `getBank(): Promise<Bank>`, `getVoyage(): Promise<Voyage | null>`, `createVoyage(): Promise<Voyage>`, `getResponses(): Promise<VoyageResponses>`, `putResponses(patch: Partial<VoyageResponses>): Promise<VoyageResponses>`, `completeSession(n: SessionId): Promise<Voyage>`, `unlockVoyage(code: string): Promise<Voyage>`, `getPortrait(): Promise<CandidatePortrait>`, `deleteVoyage(): Promise<{ message: string }>`, `missingItems(err: unknown): string[]`, `errorStatus(err: unknown): string | null`
  - `ApiError.body?: Record<string, unknown>` (widened, backward compatible)
  - CSS class `.voyage-rule`

- [ ] **Step 1: Read the Next.js proxy guide before touching `proxy.ts`**
Run: `sed -n '1,120p' /Users/imran/Downloads/design_handoff_cv_analyzer/frontend/node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/proxy.md`
Then: `sed -n '1,120p' /Users/imran/Downloads/design_handoff_cv_analyzer/frontend/node_modules/next/dist/docs/01-app/01-getting-started/16-proxy.md`
Why: this repo's `src/proxy.ts` already carries a scar from guessing — the comment at `frontend/src/proxy.ts:23-25` records that Next 16 reads `config`, not `proxyConfig`, and that under the old name the matcher was silently ignored on every request. Confirm from the doc that the file name, the exported function name `proxy`, and the exported `config.matcher` are all still what the file uses before editing it.

- [ ] **Step 2: Write `frontend/src/types/voyage.ts`**
This is contracts § I transcribed, plus the body of `sessionLock()` which § I declares but does not implement. The rules come from contracts § C.6, in that order: no voyage → order; session 0 is open as soon as the voyage exists; then code, then profile, then order.
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

/** Client-side mirror of models/voyage.session_lock(). Same order of checks:
 *  no voyage, then session 0 is always open, then code, then profile, then
 *  order. The first failing rule wins. The server enforces the same gate — this
 *  copy exists so a locked card can render its reason instead of a dead button. */
export function sessionLock(
  voyage: Voyage | null,
  profile: { prenom?: string | null; tranche_age?: string | null } | null,
  n: SessionId,
): string | null {
  if (!voyage) return LOCK_ORDER
  if (n === "0") return null
  if (!voyage.has_code) return LOCK_CODE
  if (!profile?.prenom || !profile?.tranche_age) return LOCK_PROFILE
  const previous = String(Number(n) - 1)
  if (!(voyage.sessions_completed as string[]).includes(previous)) return LOCK_ORDER
  return null
}
```

- [ ] **Step 3: Run the parity test to see it fail**
Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && ./venv/bin/python -m pytest tests/test_voyage_parity.py -v`
Expected before Step 2, and what you would have seen had you run it first: FAIL with `AssertionError: missing /Users/imran/Downloads/design_handoff_cv_analyzer/frontend/src/types/voyage.ts` — the fixture's existence assertion, mirroring `backend/tests/test_conditions_parity.py:33`.
Expected now, after Step 2: **PASS**. The three lock strings and the six `PORTRAIT_SECTIONS` keys now have their TypeScript counterpart.
If the file `tests/test_voyage_parity.py` does not exist, phase 1 has not landed yet: note it, skip to Step 4, and pick the test up again in Task 10.

- [ ] **Step 4: Widen `ApiError` so an `{errors: [...]}` body is not thrown away**
`frontend/src/lib/api.ts:43` reads `body.error ?? body.message ?? fallback`. Three voyage endpoints answer with `{"errors": [...]}` and no `error` key (contracts § E3, § E5, § E6), and so does the existing `routes/profile.upsert_profile` — today all of those surface as « Erreur inattendue. ». `POST /sessions/<n>/complete` additionally puts the missing item ids in `errors[1:]`, which the player needs to jump to them.
Replace `frontend/src/lib/api.ts:5-9`:
```ts
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    /** The parsed error body, when the server sent one. Voyage endpoints answer
     *  `{errors: [...]}` (a sentence then, for session completion, the missing
     *  item ids) and `{error, status}` for a 409 portrait — both are useful to
     *  the caller, and both used to be discarded here. */
    public body?: Record<string, unknown>,
  ) {
    super(message)
  }
}
```
Replace `frontend/src/lib/api.ts:35-44`:
```ts
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as Record<string, unknown>
    const fallback =
      res.status === 429
        ? "Trop de requêtes — patientez une minute puis réessayez."
        : res.status >= 502 && res.status <= 504
          ? "Le serveur démarre ou est temporairement indisponible. Réessayez dans 30 secondes."
          : "Erreur inattendue."
    const first = Array.isArray(body.errors) && typeof body.errors[0] === "string"
      ? (body.errors[0] as string)
      : undefined
    throw new ApiError(
      res.status,
      (body.error as string) ?? first ?? (body.message as string) ?? fallback,
      body,
    )
  }
```

- [ ] **Step 5: Write `frontend/src/lib/voyage.ts`**
```ts
/**
 * Le voyage — typed wrappers over /api/voyage.
 *
 * Mirrors backend/app/routes/voyage.py § E. The only module in the frontend
 * that knows a voyage endpoint path. Counselor endpoints (/c/<token>) belong to
 * phase 4 and are deliberately absent.
 */
import { ApiError, api } from "@/lib/api"
import type {
  Bank, BankResponse, CandidatePortrait, CandidatePortraitResponse,
  ResponsesResponse, SessionId, Voyage, VoyageResponse, VoyageResponses,
} from "@/types/voyage"

/** Text-only bank: 6 sessions, 53 items, no weights (contracts § A.4 public()). */
export const getBank = (): Promise<Bank> =>
  api.get<BankResponse>("/voyage/bank").then((r) => r.bank)

/** The open voyage, else the latest, else null. */
export const getVoyage = (): Promise<Voyage | null> =>
  api.get<VoyageResponse>("/voyage").then((r) => r.voyage)

/** Both flags are mandatory server-side; the hub's button is disabled until the
 *  person has ticked both, so they are hard-coded true here. */
export const createVoyage = (): Promise<Voyage> =>
  api.post<{ voyage: Voyage }>("/voyage", { consent: true, age_attested: true })
    .then((r) => r.voyage)

export const getResponses = (): Promise<VoyageResponses> =>
  api.get<ResponsesResponse>("/voyage/responses").then((r) => r.responses)

/** Merge semantics: supplied ids overwrite, absent ids are untouched. Returns
 *  the full merged set so a player that lost a connection can reconcile. */
export const putResponses = (patch: Partial<VoyageResponses>): Promise<VoyageResponses> =>
  api.put<ResponsesResponse>("/voyage/responses", patch).then((r) => r.responses)

export const completeSession = (n: SessionId): Promise<Voyage> =>
  api.post<{ voyage: Voyage }>(`/voyage/sessions/${n}/complete`).then((r) => r.voyage)

export const unlockVoyage = (code: string): Promise<Voyage> =>
  api.post<{ voyage: Voyage }>("/voyage/unlock", { code }).then((r) => r.voyage)

/** 200 only when portrait_status == "validated"; otherwise the server answers
 *  409 with {error, status} — read the status with errorStatus(). */
export const getPortrait = (): Promise<CandidatePortrait> =>
  api.get<CandidatePortraitResponse>("/voyage/portrait").then((r) => r.portrait)

export const deleteVoyage = (): Promise<{ message: string }> =>
  api.delete<{ message: string }>("/voyage")

/**
 * The missing item ids from a 400 on POST /sessions/<n>/complete.
 * The body is {"errors": ["Réponses manquantes.", "S1-3", "S1-5"]} — errors[0]
 * is the sentence (already the ApiError message), the rest are ids.
 */
export function missingItems(err: unknown): string[] {
  if (!(err instanceof ApiError)) return []
  const errors = err.body?.errors
  if (!Array.isArray(errors)) return []
  return errors.slice(1).filter((v): v is string => typeof v === "string")
}

/** The `status` key a 409 on GET /voyage/portrait carries. */
export function errorStatus(err: unknown): string | null {
  if (!(err instanceof ApiError)) return null
  const status = err.body?.status
  return typeof status === "string" ? status : null
}
```

- [ ] **Step 6: Add `/voyage` to `PROTECTED`**
Replace `frontend/src/proxy.ts:5`:
```ts
const PROTECTED = ["/admin", "/profil", "/voyage"]
```
Nothing else in that file changes — the `config.matcher` at `frontend/src/proxy.ts:26-28` already covers every non-static path, and the `startsWith` test at line 10 picks up `/voyage`, `/voyage/session/3` and `/voyage/portrait` alike.

- [ ] **Step 7: Add the `.voyage-rule` accent to `globals.css`**
Insert immediately after `.report-rule` (`frontend/src/app/globals.css:234-237`), before the `/* ── Print ── */` block at line 239:
```css
/* ── Le voyage ──
   The three parcours own the charter's three full-weight hues (orange, navy,
   teal). The voyage is a fourth scenario, not a fourth parcours, so instead of
   a fourth hue it takes the charter's inverted pairing: peach on navy, 6.81:1,
   the same pair the report header and the landing preview already use. */
.voyage-rule {
  height: 6px;
  background: var(--peach);
}
```

- [ ] **Step 8: Lint**
Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && npm run lint`
Expected: exit 0, no errors and no warnings for `src/types/voyage.ts`, `src/lib/voyage.ts`, `src/lib/api.ts`, `src/proxy.ts`.

- [ ] **Step 9: Build**
Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && npm run build`
Expected: `✓ Compiled successfully`, no TypeScript errors. `src/lib/voyage.ts` is unreferenced at this point — that is fine, it is a module export, not dead code eslint will flag.

- [ ] **Step 10: Commit**
```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add frontend/src/types/voyage.ts frontend/src/lib/voyage.ts frontend/src/lib/api.ts frontend/src/proxy.ts frontend/src/app/globals.css
git commit -m "feat(voyage): type the API and give the voyage its own accent

The three parcours own orange, navy and teal; the voyage takes the charter's
inverted pairing instead so it reads as a fourth scenario, not a fourth
parcours. ApiError now carries the response body, so an {errors: [...]} answer
stops collapsing into \"Erreur inattendue.\".

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015fDz83zwALmXr4REGPGH8P"
```

---

### Task 2: SessionProgress and MicroReveal

**Files:**
- Create: `frontend/src/components/voyage/SessionProgress.tsx`
- Create: `frontend/src/components/voyage/MicroReveal.tsx`
- Test: none (no frontend runner) — verified by `npm run lint`, `npm run build`, and the manual rows in Task 10

**Interfaces:**
- Consumes: `BankSession`, `SessionId`, `Voyage`, `MicroStatus`, `sessionLock()` from `@/types/voyage`; `Button` from `@/components/ui/button`; `cn` from `@/lib/utils`.
- Produces:
  - `SessionProgress({ sessions, voyage, profile, answered }): JSX.Element` where `sessions: BankSession[]`, `voyage: Voyage`, `profile: { prenom?: string | null; tranche_age?: string | null } | null`, `answered: Record<string, number>`
  - `MicroReveal({ status, phrase }): JSX.Element | null` where `status: MicroStatus`, `phrase: string | null`

- [ ] **Step 1: Write `frontend/src/components/voyage/SessionProgress.tsx`**
The session `title`, `subtitle` and `duration` are cahier text served by the API (tutoiement) and are rendered exactly as received. Everything the component adds — « Reprendre », « Commencer », « Revoir mes réponses » — is chrome, so vouvoiement. A locked row renders its reason and never a button: contracts § C.6 gives the three strings, and `sessionLock()` decides which one.
```tsx
"use client"

import Link from "next/link"
import { Check, Lock } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { sessionLock, type BankSession, type Voyage } from "@/types/voyage"

/**
 * The six stamps. One row per session: where the person is, what the cahier
 * calls it, and either a way in or the reason there is not one.
 *
 * A locked row must never render a disabled button — a dead control tells
 * nobody anything. It renders LOCK_CODE / LOCK_PROFILE / LOCK_ORDER, the same
 * strings the API returns on a 403, and the hub puts the remedy next to it.
 */
export function SessionProgress({
  sessions,
  voyage,
  profile,
  answered,
}: {
  sessions: BankSession[]
  voyage: Voyage
  profile: { prenom?: string | null; tranche_age?: string | null } | null
  /** session id -> how many of that session's items already have an answer */
  answered: Record<string, number>
}) {
  return (
    <ol className="space-y-2">
      {sessions.map((s) => {
        const done = (voyage.sessions_completed as string[]).includes(s.n)
        const lock = done ? null : sessionLock(voyage, profile, s.n)
        const count = answered[s.n] ?? 0
        const total = s.items.length

        return (
          <li
            key={s.n}
            className={cn(
              "flex flex-col gap-3 rounded-2xl p-4 ring-1 ring-foreground/10 sm:flex-row sm:items-center",
              done ? "bg-secondary/70" : "bg-card shadow-soft",
            )}
          >
            <span
              className={cn(
                "grid size-9 shrink-0 place-items-center rounded-xl font-mono text-sm font-bold",
                done
                  ? "bg-navy text-peach"
                  : lock
                    ? "bg-secondary text-muted-foreground"
                    : "bg-peach-soft text-orange-dark",
              )}
              aria-hidden
            >
              {done ? <Check className="size-4" /> : s.n}
            </span>

            <div className="min-w-0 flex-1">
              <p className="font-display text-sm font-semibold text-navy">{s.title}</p>
              <p className="text-xs leading-snug text-muted-foreground">{s.subtitle}</p>
              <p className="mt-0.5 font-mono text-[11px] text-muted-foreground">
                {s.duration}
                {!done && count > 0 ? ` · ${count} / ${total} enregistrées` : ""}
              </p>
            </div>

            {done ? (
              <Link
                href={`/voyage/session/${s.n}`}
                className="link-underline shrink-0 self-start text-xs text-navy sm:self-auto"
              >
                Revoir mes réponses
              </Link>
            ) : lock ? (
              <span className="inline-flex shrink-0 items-center gap-1.5 self-start rounded-full bg-secondary px-2.5 py-1 text-[11px] font-medium text-muted-foreground sm:self-auto">
                <Lock className="size-3" aria-hidden /> {lock}
              </span>
            ) : (
              <Button render={<Link href={`/voyage/session/${s.n}`} />} size="lg" className="shrink-0">
                {count > 0 ? "Reprendre" : "Commencer"}
              </Button>
            )}
          </li>
        )
      })}
    </ol>
  )
}
```

- [ ] **Step 2: Write `frontend/src/components/voyage/MicroReveal.tsx`**
The label is « Votre phrase ». The model-facing « Phrase révélée » of contracts § H is banned in chrome (contracts line 1618-1619) and « révélation » is on the CLAUDE.md ban list outright.
```tsx
"use client"

import { LoaderCircle, Sparkles } from "lucide-react"

import type { MicroStatus } from "@/types/voyage"

/**
 * The one sentence session 0 produces — the whole of what S0 gives back, since
 * the candidate never sees a score, a trait name or a framework name.
 *
 * Label: « Votre phrase ». The prompt-side wording (« Phrase révélée ») shares a
 * root with a banned word and never appears in the UI.
 */
export function MicroReveal({
  status,
  phrase,
}: {
  status: MicroStatus
  phrase: string | null
}) {
  if (status === "none") return null

  return (
    <div className="overflow-hidden rounded-2xl bg-navy shadow-card">
      <div className="voyage-rule" />
      <div className="px-5 py-5 sm:px-6">
        <p className="eyebrow inline-flex items-center gap-2 text-peach">
          <Sparkles className="size-3.5" aria-hidden /> Votre phrase
        </p>

        {status === "generating" && (
          <p className="mt-3 inline-flex items-center gap-2 text-sm text-white/80">
            <LoaderCircle className="size-4 animate-spin" aria-hidden />
            Nous la rédigeons. Quelques secondes.
          </p>
        )}

        {status === "success" && (
          <p className="mt-3 font-display text-lg leading-relaxed text-white">{phrase}</p>
        )}

        {status === "error" && (
          <p className="mt-3 text-sm text-white/80">
            La phrase n&apos;a pas pu être rédigée. Vos réponses sont enregistrées et la suite
            du voyage n&apos;est pas affectée.
          </p>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Lint**
Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && npm run lint`
Expected: exit 0. Watch specifically for `react/no-unescaped-entities` — every apostrophe inside JSX text must be `&apos;`, as it already is in `n&apos;a` and `n&apos;est`.

- [ ] **Step 4: Build**
Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && npm run build`
Expected: `✓ Compiled successfully`, no TypeScript errors.

- [ ] **Step 5: Commit**
```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add frontend/src/components/voyage/SessionProgress.tsx frontend/src/components/voyage/MicroReveal.tsx
git commit -m "feat(voyage): render the six stamps and the session 0 phrase

A locked session shows the reason it is locked, never a dead button.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015fDz83zwALmXr4REGPGH8P"
```

---

### Task 3: The hub — `/voyage`

**Files:**
- Create: `frontend/src/app/voyage/page.tsx`
- Test: none (no frontend runner) — manual rows 12.1–12.8 land in Task 10

**Interfaces:**
- Consumes: `getBank`, `getVoyage`, `createVoyage`, `getResponses`, `unlockVoyage`, `deleteVoyage` from `@/lib/voyage`; `SessionProgress`, `MicroReveal`; `Bank`, `Voyage`, `VoyageResponses` from `@/types/voyage`; `api`, `ApiError` from `@/lib/api`; `useAuth` from `@/lib/auth`; `AppBar`; shadcn `Alert`, `Button`, `Checkbox`, `Input`, `Skeleton`.
- Produces: route `/voyage` (default export `VoyagePage`). No exported symbols other phases consume.

- [ ] **Step 1: Read the Next.js client-component and navigation guides**
Run: `sed -n '1,140p' /Users/imran/Downloads/design_handoff_cv_analyzer/frontend/node_modules/next/dist/docs/01-app/01-getting-started/05-server-and-client-components.md`
Then: `sed -n '1,80p' /Users/imran/Downloads/design_handoff_cv_analyzer/frontend/node_modules/next/dist/docs/01-app/03-api-reference/04-functions/use-router.md`
What to confirm before writing: that `"use client"` at the top of a `page.tsx` is still how a page opts into client rendering in this version, and that `useRouter` still comes from `next/navigation` (not `next/router`). The repo's own pages do both — `frontend/src/app/profil/page.tsx:1-4` — but the AGENTS.md rule is explicit that training-data conventions are not evidence here.

- [ ] **Step 2: Write `frontend/src/app/voyage/page.tsx`**
Five things live on this page and nothing else: the consent + age gate that creates a voyage, the six-session progress, the per-state call to action, the phrase (with polling while it is being written), and the counselor-code field. Erasure sits in the footer because `DELETE /api/voyage` is otherwise unreachable and spec decision 14 promises it.
```tsx
"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { ArrowRight, KeyRound, Map as MapIcon, ShieldCheck, Trash2 } from "lucide-react"

import { AppBar } from "@/components/layout/AppBar"
import { MicroReveal } from "@/components/voyage/MicroReveal"
import { SessionProgress } from "@/components/voyage/SessionProgress"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { api, ApiError } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import {
  createVoyage, deleteVoyage, getBank, getResponses, getVoyage, unlockVoyage,
} from "@/lib/voyage"
import type { Bank, Voyage, VoyageResponses } from "@/types/voyage"

/** Haiku writes the phrase in a few seconds; the analysis waiting screen polls
 *  at the same cadence (frontend/src/app/analyse/en-cours/[id]/page.tsx:28). */
const POLL_MS = 2000

type Profile = { prenom?: string | null; tranche_age?: string | null }

/** How many of each session's items already have an answer — drives the
 *  « Reprendre » vs « Commencer » label and the per-row counter. */
function answeredBySession(
  bank: Bank | null,
  responses: VoyageResponses | null,
): Record<string, number> {
  const out: Record<string, number> = {}
  if (!bank || !responses) return out
  for (const s of bank.sessions) {
    out[s.n] = s.items.filter((it) => responses.answers[it.id] !== undefined).length
  }
  return out
}

export default function VoyagePage() {
  const router = useRouter()
  const { user, loading: authLoading } = useAuth()

  const [bank, setBank] = useState<Bank | null>(null)
  const [voyage, setVoyage] = useState<Voyage | null>(null)
  const [responses, setResponses] = useState<VoyageResponses | null>(null)
  const [profile, setProfile] = useState<Profile | null>(null)
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Consent gate
  const [consent, setConsent] = useState(false)
  const [age, setAge] = useState(false)
  const [creating, setCreating] = useState(false)

  // Counselor code
  const [code, setCode] = useState("")
  const [codeState, setCodeState] = useState<"idle" | "checking">("idle")

  // Poll retry counter — a failed poll must not silently end the loop.
  const [tick, setTick] = useState(0)

  // The proxy gates /voyage on cookie *presence*, which misses an expired
  // token. Without this, an expired session renders the consent form and only
  // fails at POST. Same guard as frontend/src/app/profil/page.tsx:104-106.
  useEffect(() => {
    if (!authLoading && !user) router.replace("/connexion?redirect=/voyage")
  }, [authLoading, user, router])

  useEffect(() => {
    let alive = true
    Promise.all([
      getBank(),
      getVoyage().catch(() => null),
      api.get<{ profile: Profile | null }>("/profile", { skipRedirect: true })
        .then((r) => r.profile)
        .catch(() => null),
    ])
      .then(async ([b, v, p]) => {
        if (!alive) return
        setBank(b)
        setVoyage(v)
        setProfile(p)
        if (v) {
          const r = await getResponses().catch(() => null)
          if (alive && r) setResponses(r)
        }
      })
      .catch((e) => {
        if (alive) setError(e instanceof ApiError ? e.message : "Erreur inattendue.")
      })
      .finally(() => { if (alive) setLoaded(true) })
    return () => { alive = false }
  }, [])

  // While the phrase or the portrait is being written, re-read the voyage every
  // 2 s. Each successful read replaces `voyage`, which re-runs this effect —
  // that is the loop, and it stops on its own when the status leaves
  // "generating". A failed read bumps `tick` so a blip does not end it.
  useEffect(() => {
    if (!voyage) return
    if (voyage.micro_status !== "generating" && voyage.portrait_status !== "generating") return
    let alive = true
    const t = setTimeout(() => {
      getVoyage()
        .then((v) => { if (alive && v) setVoyage(v) })
        .catch(() => { if (alive) setTick((n) => n + 1) })
    }, POLL_MS)
    return () => { alive = false; clearTimeout(t) }
  }, [voyage, tick])

  const start = useCallback(async () => {
    setError(null)
    setCreating(true)
    try {
      const v = await createVoyage()
      setVoyage(v)
      setResponses({ answers: {}, billets: {} })
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erreur inattendue.")
    } finally {
      setCreating(false)
    }
  }, [])

  const redeem = useCallback(async () => {
    setError(null)
    if (!code.trim()) {
      setError("Saisissez votre code conseiller.")
      return
    }
    setCodeState("checking")
    try {
      setVoyage(await unlockVoyage(code))
      setCode("")
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erreur inattendue.")
    } finally {
      setCodeState("idle")
    }
  }, [code])

  const remove = useCallback(async () => {
    if (!window.confirm(
      "Supprimer votre voyage ? Vos réponses, votre phrase et votre portrait seront effacés. Cette action est définitive.",
    )) return
    try {
      await deleteVoyage()
      setVoyage(null)
      setResponses(null)
      setConsent(false)
      setAge(false)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erreur inattendue.")
    }
  }, [])

  if (authLoading || !user || !loaded) {
    return (
      <div className="min-h-screen bg-secondary">
        <AppBar />
        <div className="mx-auto max-w-3xl px-4 py-8">
          <Skeleton className="h-9 w-64" />
          <div className="mt-6 space-y-3">
            {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-20 rounded-2xl" />)}
          </div>
        </div>
      </div>
    )
  }

  const answered = answeredBySession(bank, responses)
  const finished = voyage?.status === "termine"

  return (
    <div className="min-h-screen bg-secondary">
      <AppBar />
      <div className="voyage-rule" role="presentation" aria-hidden />

      <div className="mx-auto max-w-3xl px-4 py-8">
        <div className="mb-6">
          <p className="eyebrow inline-flex items-center gap-2 text-orange-dark">
            <MapIcon className="size-3.5" aria-hidden /> Le voyage
          </p>
          <h1 className="mt-1.5 font-display text-2xl font-bold text-navy sm:text-3xl">
            Mon cahier d&apos;exploration
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
            Six sessions pour poser ce que vous savez déjà de vous. La première prend 5 minutes
            et se fait seul ; les cinq suivantes se font avec un conseiller.
          </p>
          <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
            Aucune session n&apos;est obligatoire : vos analyses fonctionnent sans. Ce que vous
            répondez ici les rend plus précises.
          </p>
        </div>

        {error && (
          <Alert variant="destructive" className="mb-4">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* ── No voyage yet: consent + age gate ─────────────────────────── */}
        {!voyage && (
          <div className="rounded-2xl bg-card p-5 shadow-soft ring-1 ring-foreground/10 sm:p-6">
            <h2 className="font-display text-base font-semibold text-navy">Votre accord</h2>

            <label className="mt-3 flex cursor-pointer items-start gap-3 rounded-lg bg-secondary/60 p-3">
              <Checkbox className="mt-0.5" checked={consent} onCheckedChange={(v) => setConsent(v)} />
              <span className="text-xs leading-relaxed text-navy-700">
                J&apos;accepte que mes réponses au voyage soient conservées et chiffrées, et
                utilisées pour préparer mon portrait et enrichir mes analyses.
                <span className="mt-1 block text-muted-foreground">
                  Elles sont stockées séparément de mon profil. Je peux les supprimer à tout
                  moment depuis cette page, sans toucher au reste de mon compte.
                </span>
              </span>
            </label>

            <label className="mt-3 flex cursor-pointer items-start gap-3 rounded-lg bg-secondary/60 p-3">
              <Checkbox className="mt-0.5" checked={age} onCheckedChange={(v) => setAge(v)} />
              <span className="text-xs leading-relaxed text-navy-700">J&apos;ai 15 ans ou plus.</span>
            </label>

            <div className="mt-5 flex flex-col items-start justify-between gap-3 sm:flex-row sm:items-center">
              <p className="inline-flex items-center gap-2 text-xs text-muted-foreground">
                <ShieldCheck className="size-3.5 shrink-0 text-success" aria-hidden />
                Données chiffrées, supprimables à tout moment.
              </p>
              <Button size="lg" disabled={!consent || !age || creating} onClick={start}>
                {creating ? "Création…" : "Commencer le voyage"} <ArrowRight className="size-4" />
              </Button>
            </div>
          </div>
        )}

        {/* ── A voyage exists ───────────────────────────────────────────── */}
        {voyage && bank && (
          <div className="space-y-5">
            <MicroReveal status={voyage.micro_status} phrase={voyage.micro_phrase} />

            <SessionProgress
              sessions={bank.sessions}
              voyage={voyage}
              profile={profile}
              answered={answered}
            />

            {!voyage.has_code && (
              <div>
                <div className="flex flex-col gap-3 rounded-2xl bg-card p-4 ring-1 ring-foreground/10 sm:flex-row sm:items-center">
                  <span className="inline-flex shrink-0 items-center gap-2 text-sm font-medium text-navy">
                    <KeyRound className="size-4 text-orange-dark" aria-hidden />
                    Vous avez un code conseiller ?
                  </span>
                  <Input
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") redeem() }}
                    placeholder="ex. A1B2C3D4"
                    aria-label="Code conseiller"
                    className="h-10 flex-1 bg-background font-mono text-sm"
                  />
                  <Button variant="outline" size="lg" onClick={redeem} disabled={codeState === "checking"}>
                    {codeState === "checking" ? "Vérification…" : "Activer"}
                  </Button>
                </div>
                <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                  Le code ouvre les sessions 1 à 5. Il est gratuit pour les bénéficiaires
                  Cap Emploi, Mission Locale et France Travail.
                </p>
              </div>
            )}

            {!profile?.prenom || !profile?.tranche_age ? (
              <p className="text-xs leading-relaxed text-muted-foreground">
                Les sessions 1 à 5 utilisent votre prénom et votre tranche d&apos;âge.{" "}
                <Link href="/profil" className="link-underline text-navy">Compléter mon profil</Link>
                {" "}— une information, une seule fois.
              </p>
            ) : null}

            {/* Portrait */}
            {voyage.portrait_status === "validated" && (
              <div className="flex flex-col items-start justify-between gap-3 rounded-2xl bg-navy p-5 sm:flex-row sm:items-center">
                <div>
                  <p className="eyebrow text-peach">Votre portrait</p>
                  <p className="mt-1 font-display text-base font-bold text-white">
                    Relu et validé par votre conseiller.
                  </p>
                </div>
                <Button
                  render={<Link href="/voyage/portrait" />}
                  size="lg"
                  className="shrink-0 bg-white text-navy hover:bg-white/90"
                >
                  Voir mon portrait <ArrowRight className="size-4" />
                </Button>
              </div>
            )}

            {finished && (voyage.portrait_status === "generating" || voyage.portrait_status === "draft") && (
              <p className="rounded-2xl bg-card p-4 text-sm leading-relaxed text-muted-foreground ring-1 ring-foreground/10">
                Votre portrait est rédigé et attend la validation de votre conseiller. Vous y aurez
                accès dès qu&apos;il l&apos;aura relu avec vous.
              </p>
            )}

            {finished && voyage.portrait_status === "error" && (
              <p className="rounded-2xl bg-card p-4 text-sm leading-relaxed text-muted-foreground ring-1 ring-foreground/10">
                Votre portrait n&apos;a pas pu être rédigé. Votre conseiller peut le relancer.
              </p>
            )}

            <div className="pt-2">
              <button
                type="button"
                onClick={remove}
                className="inline-flex items-center gap-1.5 text-xs text-muted-foreground underline-offset-2 hover:text-destructive hover:underline"
              >
                <Trash2 className="size-3.5" aria-hidden /> Supprimer mon voyage
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Lint**
Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && npm run lint`
Expected: exit 0. The mount-only loader effect has an empty dependency array on purpose; if `react-hooks/exhaustive-deps` warns, silence it exactly as the repo already does at `frontend/src/app/profil/page.tsx:133` with `// eslint-disable-next-line react-hooks/exhaustive-deps` on the line above the `}, [])`.

- [ ] **Step 4: Build**
Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && npm run build`
Expected: `✓ Compiled successfully`; the route list includes `/voyage`.

- [ ] **Step 5: Manual check — the gate and the lock reasons**
Start the stack (`docker compose up -d`, then http://localhost:8080) and log in as a candidate with no voyage and an empty profile.
1. Open `/voyage`. Expect: « Mon cahier d'exploration », the two checkboxes, and « Commencer le voyage » greyed out.
2. Tick only « J'ai 15 ans ou plus ». Expect: the button stays greyed out.
3. Tick both. Expect: the button becomes active. Click it.
4. Expect: the six session rows appear. Row 0 shows a « Commencer » button. Rows 1–5 each show a grey pill reading **« Avec un conseiller »** and no button at all.
5. Enter a valid counselor code and click « Activer ». Expect: the code field disappears and rows 1–5 now read **« Complétez votre profil »** (the profile is still empty).
6. Fill prénom and tranche d'âge at `/profil`, come back to `/voyage`. Expect: row 1 shows « Commencer »; rows 2–5 read **« Terminez la session précédente »**.
7. Log out and open `/voyage`. Expect: redirected to `/connexion?redirect=/voyage`.

- [ ] **Step 6: Commit**
```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add frontend/src/app/voyage/page.tsx
git commit -m "feat(voyage): the hub — consent gate, six stamps, code entry, phrase

Polls GET /api/voyage every 2 s while the phrase or the portrait is being
written, and stops on its own when the status leaves generating.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015fDz83zwALmXr4REGPGH8P"
```

---

### Task 4: The player's atoms — ChecklistRow, OptionCard, SceneCard

**Files:**
- Create: `frontend/src/components/voyage/ChecklistRow.tsx`
- Create: `frontend/src/components/voyage/OptionCard.tsx`
- Create: `frontend/src/components/voyage/SceneCard.tsx`
- Test: none (no frontend runner)

**Interfaces:**
- Consumes: `BankScene` from `@/types/voyage`; `cn` from `@/lib/utils`; `Check`, `X` from `lucide-react`.
- Produces:
  - `ChecklistRow({ n, text, value, disabled, onChange })` — `n: number`, `text: string`, `value: boolean | undefined`, `disabled?: boolean`, `onChange: (next: boolean) => void`
  - `OptionCard({ letter, label, text, selected, disabled, onSelect })` — all `string` except `selected: boolean`, `disabled?: boolean`, `onSelect: () => void`
  - `SceneCard({ scene, value, disabled, onSelect })` — `scene: BankScene`, `value?: string`, `disabled?: boolean`, `onSelect: (letter: string) => void`

- [ ] **Step 1: Write `frontend/src/components/voyage/ChecklistRow.tsx`**
The cahier prints a ✓ box and a ✗ box on each of the 20 lines and asks for an instinctive pass. Two explicit buttons keep that shape, and they make « not answered yet » visible — a single checkbox cannot, and the completion endpoint rejects a session with any item unanswered (contracts § E6).
```tsx
"use client"

import { Check, X } from "lucide-react"

import { cn } from "@/lib/utils"

/**
 * One session-0 affirmation with its OUI / NON pair.
 *
 * Two buttons rather than one checkbox: the cahier prints two boxes, and the
 * completion endpoint refuses a session that still has an unanswered item, so
 * "not answered yet" has to be a state the person can see.
 */
export function ChecklistRow({
  n,
  text,
  value,
  disabled,
  onChange,
}: {
  n: number
  text: string
  value: boolean | undefined
  disabled?: boolean
  onChange: (next: boolean) => void
}) {
  return (
    <div
      className={cn(
        "flex items-center gap-3 rounded-xl px-3 py-2.5 ring-1 transition-colors",
        value === undefined
          ? "bg-secondary/60 ring-foreground/5"
          : "bg-card ring-foreground/10",
      )}
    >
      <span className="w-5 shrink-0 font-mono text-[11px] text-muted-foreground">{n}</span>
      <p className="min-w-0 flex-1 text-sm leading-snug text-navy">{text}</p>

      <div className="flex shrink-0 gap-1.5">
        <button
          type="button"
          disabled={disabled}
          aria-pressed={value === true}
          aria-label={`Oui — ${text}`}
          onClick={() => onChange(true)}
          className={cn(
            "grid size-9 place-items-center rounded-lg border transition-colors disabled:cursor-not-allowed disabled:opacity-50",
            value === true
              ? "border-success bg-success text-white"
              : "border-input text-muted-foreground hover:border-success/60 hover:text-success",
          )}
        >
          <Check className="size-4" aria-hidden />
        </button>

        <button
          type="button"
          disabled={disabled}
          aria-pressed={value === false}
          aria-label={`Non — ${text}`}
          onClick={() => onChange(false)}
          className={cn(
            "grid size-9 place-items-center rounded-lg border transition-colors disabled:cursor-not-allowed disabled:opacity-50",
            value === false
              ? "border-navy bg-navy text-white"
              : "border-input text-muted-foreground hover:border-navy/60 hover:text-navy",
          )}
        >
          <X className="size-4" aria-hidden />
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Write `frontend/src/components/voyage/OptionCard.tsx`**
```tsx
"use client"

import { cn } from "@/lib/utils"

/**
 * One lettered option of one scene. `label` and `text` are cahier and counselor-
 * manual wording served by the API — rendered as received, tutoiement included.
 * The scoring tag behind the option never leaves the server (spec decision 6).
 */
export function OptionCard({
  letter,
  label,
  text,
  selected,
  disabled,
  onSelect,
}: {
  letter: string
  label: string
  text: string
  selected: boolean
  disabled?: boolean
  onSelect: () => void
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      aria-pressed={selected}
      onClick={onSelect}
      className={cn(
        "flex w-full gap-3 rounded-xl border p-3.5 text-left transition-colors",
        "disabled:cursor-not-allowed disabled:opacity-70",
        selected
          ? "border-navy bg-navy/5 ring-1 ring-navy"
          : "border-input bg-card hover:border-peach hover:bg-peach-soft/30",
      )}
    >
      <span
        className={cn(
          "grid size-7 shrink-0 place-items-center rounded-lg font-mono text-xs font-bold",
          selected ? "bg-navy text-peach" : "bg-secondary text-muted-foreground",
        )}
        aria-hidden
      >
        {letter}
      </span>
      <span className="min-w-0">
        <span className="block font-display text-sm font-semibold text-navy">{label}</span>
        <span className="mt-0.5 block text-sm leading-snug text-navy-700">{text}</span>
      </span>
    </button>
  )
}
```

- [ ] **Step 3: Write `frontend/src/components/voyage/SceneCard.tsx`**
```tsx
"use client"

import { OptionCard } from "@/components/voyage/OptionCard"
import type { BankScene } from "@/types/voyage"

/**
 * One scene, one screen. Title, subtitle, narrative, question and options are
 * the cahier's own text (tutoiement), served by GET /api/voyage/bank and
 * rendered verbatim — spec decision 15.
 */
export function SceneCard({
  scene,
  value,
  disabled,
  onSelect,
}: {
  scene: BankScene
  value?: string
  disabled?: boolean
  onSelect: (letter: string) => void
}) {
  return (
    <article className="overflow-hidden rounded-2xl bg-card shadow-soft ring-1 ring-foreground/10">
      <div className="voyage-rule" />
      <div className="p-5 sm:p-6">
        <h2 className="font-display text-xl font-bold leading-tight text-navy">{scene.title}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{scene.subtitle}</p>

        {scene.narrative.length > 0 && (
          <div className="mt-4 space-y-2.5 rounded-xl bg-secondary/60 p-4">
            {scene.narrative.map((paragraph, i) => (
              <p key={i} className="text-sm leading-relaxed text-navy-700">{paragraph}</p>
            ))}
          </div>
        )}

        <p className="mt-5 font-display text-base font-semibold text-navy">{scene.question}</p>

        <div className="mt-3 space-y-2">
          {scene.options.map((o) => (
            <OptionCard
              key={o.letter}
              letter={o.letter}
              label={o.label}
              text={o.text}
              selected={value === o.letter}
              disabled={disabled}
              onSelect={() => onSelect(o.letter)}
            />
          ))}
        </div>
      </div>
    </article>
  )
}
```

- [ ] **Step 4: Lint**
Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && npm run lint`
Expected: exit 0.

- [ ] **Step 5: Build**
Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && npm run build`
Expected: `✓ Compiled successfully`.

- [ ] **Step 6: Commit**
```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add frontend/src/components/voyage/ChecklistRow.tsx frontend/src/components/voyage/OptionCard.tsx frontend/src/components/voyage/SceneCard.tsx
git commit -m "feat(voyage): the player's atoms — checklist row, option, scene

Two buttons per affirmation rather than one checkbox, so \"not answered yet\"
is a state the person can see.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015fDz83zwALmXr4REGPGH8P"
```

---

### Task 5: BilletForm

**Files:**
- Create: `frontend/src/components/voyage/BilletForm.tsx`
- Test: none (no frontend runner)

**Interfaces:**
- Consumes: `BankBilletField` from `@/types/voyage`; `Label` from `@/components/ui/label`; `Textarea` from `@/components/ui/textarea`.
- Produces: `BilletForm({ fields, values, disabled, onChange })` — `fields: BankBilletField[]`, `values: Record<string, string>`, `disabled?: boolean`, `onChange: (key: string, next: string) => void`

- [ ] **Step 1: Write `frontend/src/components/voyage/BilletForm.tsx`**
The 20 billet fields are optional everywhere (contracts § A.3: 2 + 4 + 3 + 3 + 4 + 4 fields, `label` verbatim cahier including its trailing « : »). `POST /sessions/<n>/complete` checks scored items only, never billets, so nothing here may be marked required.
```tsx
"use client"

import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import type { BankBilletField } from "@/types/voyage"

/**
 * The billet de sortie. Every field is optional — session completion checks the
 * scored items only — and each label is the cahier's own line, trailing colon
 * included, served by GET /api/voyage/bank.
 */
export function BilletForm({
  fields,
  values,
  disabled,
  onChange,
}: {
  fields: BankBilletField[]
  values: Record<string, string>
  disabled?: boolean
  onChange: (key: string, next: string) => void
}) {
  if (fields.length === 0) return null

  return (
    <div className="space-y-4">
      {fields.map((f) => (
        <div key={f.key}>
          <Label htmlFor={`billet-${f.key}`} className="block text-sm leading-snug text-navy">
            {f.label}
          </Label>
          <Textarea
            id={`billet-${f.key}`}
            rows={3}
            disabled={disabled}
            value={values[f.key] ?? ""}
            onChange={(e) => onChange(f.key, e.target.value)}
            className="mt-1.5 bg-card"
          />
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 2: Lint**
Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && npm run lint`
Expected: exit 0.

- [ ] **Step 3: Build**
Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && npm run build`
Expected: `✓ Compiled successfully`.

- [ ] **Step 4: Commit**
```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add frontend/src/components/voyage/BilletForm.tsx
git commit -m "feat(voyage): the billet de sortie, optional everywhere

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015fDz83zwALmXr4REGPGH8P"
```

---

### Task 6: The player — `/voyage/session/[n]`

**Files:**
- Create: `frontend/src/app/voyage/session/[n]/page.tsx`
- Test: none (no frontend runner) — manual rows 12.9–12.16 land in Task 10

**Interfaces:**
- Consumes: `getBank`, `getVoyage`, `getResponses`, `putResponses`, `completeSession`, `missingItems` from `@/lib/voyage`; `SceneCard`, `ChecklistRow`, `BilletForm`; `isScene`, `sessionLock`, `BankChecklistItem`, `BankSession`, `SessionId`, `Voyage`, `VoyageAnswer`, `VoyageResponses` from `@/types/voyage`; `useParams`, `useRouter` from `next/navigation`.
- Produces: route `/voyage/session/[n]` (default export `SessionPlayerPage`). No exported symbols other phases consume.

- [ ] **Step 1: Read the Next.js dynamic-segment guide before writing the route**
Run: `sed -n '1,110p' /Users/imran/Downloads/design_handoff_cv_analyzer/frontend/node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/dynamic-routes.md`
Then: `sed -n '1,70p' /Users/imran/Downloads/design_handoff_cv_analyzer/frontend/node_modules/next/dist/docs/01-app/03-api-reference/04-functions/use-params.md`
What this settles: in this version `params` reaches a **page** as a `Promise`, unwrapped with `await` in a server component or React's `use()` in a client one — but a client component may equally read the filled-in segment with `useParams<{ n: string }>()` from `next/navigation`, which is what this repo already does at `frontend/src/app/analyse/[id]/rapport/page.tsx:21` and `frontend/src/app/analyse/en-cours/[id]/page.tsx:44`. This plan uses `useParams`, matching the repo. Do not reach for `params` as a plain object — that shape is gone.

- [ ] **Step 2: Write `frontend/src/app/voyage/session/[n]/page.tsx`**
Behaviour this file has to get exactly right, all four pinned by the brief:
1. **Save on every « Suivant »**, merge semantics — `PUT /responses` with only the ids touched on the screen you are leaving. The S0 checklist is one screen for twenty rows, so a per-row `PUT` fires on every toggle as well: that is what makes the promise « a dropped connection loses one scene, not a session » true for session 0 too. Writes go through a single promise chain so two toggles of the same row cannot land out of order.
2. **Resume on the first unanswered item.** All answered → the billet screen.
3. **A locked session renders its reason**, never a dead button.
4. **A completed session is read-only**: inputs disabled, « Terminer » replaced by « Retour au voyage ». Re-answering a scored session after completion would silently change a scoring the counselor may already have restituted.
```tsx
"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"
import { ArrowLeft, ArrowRight, Check, Lock } from "lucide-react"

import { AppBar } from "@/components/layout/AppBar"
import { BilletForm } from "@/components/voyage/BilletForm"
import { ChecklistRow } from "@/components/voyage/ChecklistRow"
import { SceneCard } from "@/components/voyage/SceneCard"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { api, ApiError } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import {
  completeSession, getBank, getResponses, getVoyage, missingItems, putResponses,
} from "@/lib/voyage"
import {
  isScene, sessionLock,
  type BankChecklistItem, type BankSession,
  type Voyage, type VoyageAnswer, type VoyageResponses,
} from "@/types/voyage"

type Profile = { prenom?: string | null; tranche_age?: string | null }

const asBool = (v: VoyageAnswer | undefined) => (typeof v === "boolean" ? v : undefined)
const asLetter = (v: VoyageAnswer | undefined) => (typeof v === "string" ? v : undefined)

/** The step to land on when resuming: the first item with no answer, or the
 *  billet screen when every item is answered. */
function resumeStep(session: BankSession, answers: Record<string, VoyageAnswer>): number {
  if (session.kind === "checklist") {
    return session.items.every((it) => answers[it.id] !== undefined) ? 1 : 0
  }
  const idx = session.items.findIndex((it) => answers[it.id] === undefined)
  return idx === -1 ? session.items.length : idx
}

export default function SessionPlayerPage() {
  const { n } = useParams<{ n: string }>()
  const router = useRouter()
  const { user, loading: authLoading } = useAuth()

  const [session, setSession] = useState<BankSession | null>(null)
  const [voyage, setVoyage] = useState<Voyage | null>(null)
  const [profile, setProfile] = useState<Profile | null>(null)
  const [answers, setAnswers] = useState<Record<string, VoyageAnswer>>({})
  const [billets, setBillets] = useState<Record<string, string>>({})
  const [step, setStep] = useState(0)
  const [loaded, setLoaded] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notFound, setNotFound] = useState(false)

  // One promise chain for every write, so two rapid toggles of the same item
  // cannot land out of order. Each link swallows its own rejection — a single
  // failure must not poison the chain for the rest of the session — and
  // reports success as a boolean, because the caller has to know whether it is
  // allowed to advance.
  const chain = useRef<Promise<unknown>>(Promise.resolve())
  const save = useCallback((patch: Partial<VoyageResponses>): Promise<boolean> => {
    const next = chain.current
      .then(() => putResponses(patch))
      .then(() => { setError(null); return true })
      .catch((e: unknown) => {
        setError(e instanceof ApiError
          ? e.message
          : "Enregistrement impossible. Vérifiez votre connexion.")
        return false
      })
    chain.current = next
    return next
  }, [])

  useEffect(() => {
    if (!authLoading && !user) router.replace(`/connexion?redirect=/voyage/session/${n}`)
  }, [authLoading, user, router, n])

  useEffect(() => {
    let alive = true
    Promise.all([
      getBank(),
      getVoyage().catch(() => null),
      getResponses().catch(() => null),
      api.get<{ profile: Profile | null }>("/profile", { skipRedirect: true })
        .then((r) => r.profile)
        .catch(() => null),
    ])
      .then(([bank, v, r, p]) => {
        if (!alive) return
        const s = bank.sessions.find((x) => x.n === n) ?? null
        if (!s) { setNotFound(true); return }
        const a = r?.answers ?? {}
        setSession(s)
        setVoyage(v)
        setProfile(p)
        setAnswers(a)
        setBillets(r?.billets?.[n] ?? {})
        setStep(resumeStep(s, a))
      })
      .catch((e) => {
        if (alive) setError(e instanceof ApiError ? e.message : "Erreur inattendue.")
      })
      .finally(() => { if (alive) setLoaded(true) })
    return () => { alive = false }
  }, [n])

  const scenes = useMemo(() => (session ? session.items.filter(isScene) : []), [session])
  const rows = useMemo(
    () => (session
      ? session.items.filter((it): it is BankChecklistItem => !isScene(it))
      : []),
    [session],
  )

  const done = session && voyage
    ? (voyage.sessions_completed as string[]).includes(session.n)
    : false
  const lock = session ? sessionLock(voyage, profile, session.n) : null
  const lastStep = session ? (session.kind === "checklist" ? 1 : session.items.length) : 0
  const onBillet = step >= lastStep

  const setAnswer = useCallback((id: string, value: VoyageAnswer) => {
    setAnswers((prev) => ({ ...prev, [id]: value }))
  }, [])

  /** Session 0 only: persist the row the moment it is toggled, so a dropped
   *  connection costs one affirmation and not the whole twenty-row screen. */
  const toggleRow = useCallback((id: string, value: boolean) => {
    setAnswer(id, value)
    void save({ answers: { [id]: value } })
  }, [save, setAnswer])

  const next = useCallback(async () => {
    if (!session) return
    setBusy(true)
    try {
      let ok: boolean
      if (session.kind === "checklist") {
        // Reconcile the whole screen: individual rows were already sent, this
        // catches anything a failed per-row write left behind.
        const patch: Record<string, VoyageAnswer> = {}
        for (const it of session.items) {
          if (answers[it.id] !== undefined) patch[it.id] = answers[it.id]
        }
        ok = await save({ answers: patch })
      } else {
        const item = session.items[step]
        if (!item) return
        if (answers[item.id] === undefined) {
          setError("Choisissez une réponse pour continuer.")
          return
        }
        ok = await save({ answers: { [item.id]: answers[item.id] } })
      }
      // A failed write must not advance: the promise is « a dropped connection
      // loses one scene, not a session », and advancing would lose this one.
      if (!ok) return
      setStep((s) => Math.min(s + 1, lastStep))
      window.scrollTo({ top: 0, behavior: "smooth" })
    } finally {
      setBusy(false)
    }
  }, [answers, lastStep, save, session, step])

  const back = useCallback(() => {
    setError(null)
    setStep((s) => Math.max(0, s - 1))
    window.scrollTo({ top: 0, behavior: "smooth" })
  }, [])

  const finish = useCallback(async () => {
    if (!session) return
    setBusy(true)
    setError(null)
    // save() swallows its own rejection and reports a boolean, so the billet
    // write is checked here rather than by the try/catch below.
    const saved = await save({ billets: { [session.n]: billets } })
    if (!saved) { setBusy(false); return }
    try {
      await completeSession(session.n)
      router.push("/voyage")
    } catch (e) {
      const missing = missingItems(e)
      setError(e instanceof ApiError ? e.message : "Erreur inattendue.")
      if (missing.length > 0 && session.kind !== "checklist") {
        const idx = session.items.findIndex((it) => it.id === missing[0])
        if (idx >= 0) setStep(idx)
      } else if (missing.length > 0) {
        setStep(0)
        window.setTimeout(() => {
          document.getElementById(`item-${missing[0]}`)
            ?.scrollIntoView({ behavior: "smooth", block: "center" })
        }, 100)
      }
      setBusy(false)
    }
  }, [billets, router, save, session])

  if (authLoading || !user || !loaded) {
    return (
      <div className="min-h-screen bg-secondary">
        <AppBar />
        <div className="mx-auto max-w-2xl px-4 py-8">
          <Skeleton className="h-9 w-56" />
          <Skeleton className="mt-6 h-72 rounded-2xl" />
        </div>
      </div>
    )
  }

  if (notFound || !session) {
    return (
      <div className="min-h-screen bg-secondary">
        <AppBar />
        <div className="mx-auto max-w-2xl px-4 py-16 text-center">
          <p className="font-display text-lg font-bold text-navy">Session inconnue.</p>
          <Button render={<Link href="/voyage" />} size="lg" className="mt-4">
            Retour au voyage
          </Button>
        </div>
      </div>
    )
  }

  if (lock) {
    return (
      <div className="min-h-screen bg-secondary">
        <AppBar />
        <div className="voyage-rule" role="presentation" aria-hidden />
        <div className="mx-auto max-w-2xl px-4 py-16 text-center">
          <span className="mx-auto grid size-12 place-items-center rounded-full bg-secondary text-muted-foreground">
            <Lock className="size-5" aria-hidden />
          </span>
          <p className="mt-4 font-display text-lg font-bold text-navy">{lock}</p>
          <p className="mt-2 text-sm text-muted-foreground">
            Cette session n&apos;est pas encore ouverte. Revenez au voyage pour voir ce qu&apos;il
            manque.
          </p>
          <Button render={<Link href="/voyage" />} size="lg" className="mt-5">
            Retour au voyage
          </Button>
        </div>
      </div>
    )
  }

  const scene = session.kind === "scenes" ? scenes[step] : undefined
  const position = onBillet
    ? "Billet de sortie"
    : session.kind === "checklist"
      ? `${session.items.length} affirmations`
      : `Scène ${step + 1} sur ${scenes.length}`

  return (
    <div className="min-h-screen bg-secondary">
      <AppBar />
      <div className="voyage-rule" role="presentation" aria-hidden />

      <div className="mx-auto max-w-2xl px-4 py-8">
        <div className="mb-5">
          <Link
            href="/voyage"
            className="inline-flex items-center gap-1.5 text-xs text-muted-foreground underline-offset-2 hover:underline"
          >
            <ArrowLeft className="size-3.5" aria-hidden /> Le voyage
          </Link>
          <p className="eyebrow mt-3 text-orange-dark">Session {session.n}</p>
          <h1 className="mt-1 font-display text-2xl font-bold text-navy sm:text-3xl">
            {session.title}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">{session.subtitle}</p>
          <p className="mt-1.5 font-mono text-[11px] text-muted-foreground">
            {session.duration} · {position}
          </p>
        </div>

        {done && (
          <Alert className="mb-4">
            <AlertDescription>
              Session terminée. Vous pouvez la relire ; les réponses ne sont plus modifiables.
            </AlertDescription>
          </Alert>
        )}

        {error && (
          <Alert variant="destructive" className="mb-4">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Session intro — first screen only */}
        {step === 0 && session.intro.length > 0 && (
          <div className="mb-5 space-y-2.5 rounded-2xl bg-card p-5 shadow-soft ring-1 ring-foreground/10">
            {session.intro.map((paragraph, i) => (
              <p key={i} className="text-sm leading-relaxed text-navy-700">{paragraph}</p>
            ))}
          </div>
        )}

        {/* ── Session 0: one scrolling list of 20 rows ─────────────────── */}
        {!onBillet && session.kind === "checklist" && (
          <div className="space-y-1.5">
            {rows.map((item, i) => (
              <div key={item.id} id={`item-${item.id}`}>
                <ChecklistRow
                  n={i + 1}
                  text={item.text}
                  value={asBool(answers[item.id])}
                  disabled={done}
                  onChange={(v) => toggleRow(item.id, v)}
                />
              </div>
            ))}
          </div>
        )}

        {/* ── Sessions 1–5: one scene per screen ──────────────────────── */}
        {!onBillet && session.kind === "scenes" && scene && (
          <div id={`item-${scene.id}`}>
            <SceneCard
              scene={scene}
              value={asLetter(answers[scene.id])}
              disabled={done}
              onSelect={(letter) => setAnswer(scene.id, letter)}
            />
          </div>
        )}

        {/* ── Last screen: outro + the optional billet ─────────────────── */}
        {onBillet && (
          <div className="space-y-5">
            {session.outro.length > 0 && (
              <div className="space-y-2.5 rounded-2xl bg-card p-5 shadow-soft ring-1 ring-foreground/10">
                {session.outro.map((paragraph, i) => (
                  <p key={i} className="text-sm leading-relaxed text-navy-700">{paragraph}</p>
                ))}
              </div>
            )}

            <div className="rounded-2xl bg-card p-5 shadow-soft ring-1 ring-foreground/10 sm:p-6">
              <h2 className="font-display text-base font-semibold text-navy">Billet de sortie</h2>
              <p className="mb-4 mt-1 text-xs text-muted-foreground">
                Facultatif. Rien ici n&apos;est noté ni comparé.
              </p>
              <BilletForm
                fields={session.billet}
                values={billets}
                disabled={done}
                onChange={(key, value) => setBillets((prev) => ({ ...prev, [key]: value }))}
              />
            </div>
          </div>
        )}

        {/* ── Navigation ───────────────────────────────────────────────── */}
        <div className="mt-6 flex items-center justify-between gap-3">
          <Button variant="outline" size="lg" onClick={back} disabled={step === 0 || busy}>
            <ArrowLeft className="size-4" /> Précédent
          </Button>

          {!onBillet ? (
            <Button size="lg" onClick={next} disabled={busy}>
              {busy ? "Enregistrement…" : "Suivant"} <ArrowRight className="size-4" />
            </Button>
          ) : done ? (
            <Button render={<Link href="/voyage" />} size="lg">
              Retour au voyage <ArrowRight className="size-4" />
            </Button>
          ) : (
            <Button size="lg" onClick={finish} disabled={busy}>
              {busy ? "Enregistrement…" : "Terminer"} <Check className="size-4" />
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Lint**
Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && npm run lint`
Expected: exit 0. If `react-hooks/exhaustive-deps` warns about the loader effect's `[n]` array, add `// eslint-disable-next-line react-hooks/exhaustive-deps` above the closing `}, [n])`, as `frontend/src/app/profil/page.tsx:133` already does.

- [ ] **Step 4: Build**
Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && npm run build`
Expected: `✓ Compiled successfully`; the route list includes `/voyage/session/[n]`.

- [ ] **Step 5: Manual check — save, resume and the lock**
With a voyage created and a valid counselor code redeemed:
1. Open `/voyage/session/0`. Expect: the session intro, then a single scrolling list of 20 rows, each with a ✓ and a ✗.
2. Answer rows 1–5, then reload the page. Expect: the five answers are still selected — they were saved on toggle, not on « Suivant ».
3. Answer all 20 and click « Suivant ». Expect: the billet screen with two labelled textareas.
4. Click « Terminer ». Expect: back on `/voyage`, row 0 stamped with a check and « Votre phrase » showing a spinner, then a sentence within a few seconds.
5. Open `/voyage/session/1`, answer scenes 1 and 2, then close the tab mid-scene 3. Reopen `/voyage/session/1`. Expect: it lands on **scene 3**, with scenes 1 and 2 already answered.
6. On any scene, click « Suivant » without choosing an option. Expect: « Choisissez une réponse pour continuer. » and the screen does not advance.
7. Open `/voyage/session/4` while session 3 is unfinished. Expect: a lock screen reading **« Terminez la session précédente »** and a « Retour au voyage » button — no player, no dead « Suivant ».
8. Reopen `/voyage/session/0` after finishing it. Expect: the amber-free info banner « Session terminée… », the ✓ / ✗ buttons greyed out, and « Retour au voyage » where « Terminer » was.

- [ ] **Step 6: Commit**
```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add "frontend/src/app/voyage/session/[n]/page.tsx"
git commit -m "feat(voyage): the player — one scene per screen, resume, billet

Answers PUT on every Suivant with merge semantics; session 0's twenty rows also
save on toggle, so a dropped connection costs one affirmation and not the
screen. Resume lands on the first unanswered item.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015fDz83zwALmXr4REGPGH8P"
```

---

### Task 7: The portrait — `/voyage/portrait`

**Files:**
- Create: `frontend/src/app/voyage/portrait/page.tsx`
- Test: none (no frontend runner) — manual rows 12.17–12.19 land in Task 10

**Interfaces:**
- Consumes: `getPortrait`, `errorStatus` from `@/lib/voyage`; `PORTRAIT_SECTIONS`, `CandidatePortrait` from `@/types/voyage`; `Logo` from `@/components/brand/Logo`; `.report-shell`, `.report-rule`'s sibling `.voyage-rule`, `.no-print` from `globals.css`.
- Produces: route `/voyage/portrait` (default export `VoyagePortraitPage`).

- [ ] **Step 1: Write `frontend/src/app/voyage/portrait/page.tsx`**
The page only ever renders a **validated** portrait; every other state is the server's 409, whose body carries `status` (contracts § E8). The A4 shell, the print rules and `.no-print` already exist in `frontend/src/app/globals.css:220-261` and are reused unchanged — the only difference from the analysis report is the accent rule.
```tsx
"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { ArrowLeft, Printer } from "lucide-react"

import { AppBar } from "@/components/layout/AppBar"
import { Logo } from "@/components/brand/Logo"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { api, ApiError } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { errorStatus, getPortrait } from "@/lib/voyage"
import { PORTRAIT_SECTIONS, type CandidatePortrait } from "@/types/voyage"

/** What to say for each portrait_status the 409 can carry. Chrome, so
 *  vouvoiement — the portrait's own six sections stay tutoiement. */
const PENDING: Record<string, string> = {
  none: "Votre portrait n'a pas encore été rédigé. Il arrive une fois les six sessions terminées.",
  generating: "Votre portrait est en cours de rédaction.",
  draft: "Votre portrait est rédigé et attend la validation de votre conseiller. Vous y aurez accès dès qu'il l'aura relu avec vous.",
  error: "Votre portrait n'a pas pu être rédigé. Votre conseiller peut le relancer.",
}

type Profile = { prenom?: string | null }

export default function VoyagePortraitPage() {
  const router = useRouter()
  const { user, loading: authLoading } = useAuth()

  const [portrait, setPortrait] = useState<CandidatePortrait | null>(null)
  const [pending, setPending] = useState<string | null>(null)
  const [prenom, setPrenom] = useState<string>("")
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!authLoading && !user) router.replace("/connexion?redirect=/voyage/portrait")
  }, [authLoading, user, router])

  useEffect(() => {
    let alive = true
    api.get<{ profile: Profile | null }>("/profile", { skipRedirect: true })
      .then((r) => { if (alive) setPrenom(r.profile?.prenom ?? "") })
      .catch(() => {})

    getPortrait()
      .then((p) => { if (alive) setPortrait(p) })
      .catch((e) => {
        if (!alive) return
        const status = errorStatus(e)
        setPending(
          (status && PENDING[status]) ??
          (e instanceof ApiError ? e.message : "Erreur inattendue."),
        )
      })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [])

  if (authLoading || !user || loading) {
    return (
      <div className="min-h-screen bg-secondary">
        <AppBar />
        <div className="px-4 py-8">
          <Skeleton className="mx-auto h-[600px] w-[620px] max-w-full rounded-xl" />
        </div>
      </div>
    )
  }

  if (!portrait) {
    return (
      <div className="min-h-screen bg-secondary">
        <AppBar />
        <div className="mx-auto max-w-2xl px-4 py-16 text-center">
          <p className="font-display text-lg font-bold text-navy">Votre portrait</p>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{pending}</p>
          <Button render={<Link href="/voyage" />} size="lg" className="mt-5">
            Retour au voyage
          </Button>
        </div>
      </div>
    )
  }

  const validated = portrait.validated_at
    ? new Date(portrait.validated_at).toLocaleDateString("fr-FR", {
        day: "2-digit", month: "long", year: "numeric",
      })
    : ""

  return (
    <div className="min-h-screen bg-secondary">
      <AppBar />

      <div className="no-print sticky top-20 z-40 flex flex-wrap items-center justify-center gap-2 border-b border-border bg-secondary/95 py-3 backdrop-blur-sm">
        <Button
          render={<Link href="/voyage" />}
          variant="outline"
          size="sm"
        >
          <ArrowLeft className="size-3.5" /> Le voyage
        </Button>
        <Button variant="outline" size="sm" onClick={() => setTimeout(() => window.print(), 50)}>
          <Printer className="size-3.5" /> PDF
        </Button>
      </div>

      <div className="px-4 py-8">
        <div className="report-shell">
          <div className="voyage-rule" />

          <div className="bg-navy px-8 pb-6 pt-6 text-white">
            <Logo tone="light" className="text-base" />
            <h1 className="mt-3 font-display text-2xl font-extrabold leading-tight text-white">
              {prenom || "Votre portrait"}
            </h1>
            <p className="mt-1 text-sm italic text-peach">
              Portrait du voyage{validated ? ` · validé le ${validated}` : ""}
            </p>
          </div>

          <div className="px-8 py-7">
            {PORTRAIT_SECTIONS.map(({ key, title }) => {
              const body = portrait.sections[key]
              if (!body) return null
              return (
                <section key={key} className="print-break mb-7 last:mb-0">
                  <h2 className="mb-2 font-display text-sm font-semibold uppercase tracking-wide text-navy">
                    {title}
                  </h2>
                  <p
                    className={
                      key === "accroche"
                        ? "whitespace-pre-line font-display text-lg italic leading-relaxed text-navy"
                        : "whitespace-pre-line text-sm leading-relaxed text-navy-700"
                    }
                  >
                    {body}
                  </p>
                </section>
              )
            })}

            <div className="mt-8 flex items-center justify-between border-t border-border pt-4">
              <span className="font-mono text-[10px] text-muted-foreground">neoori · confidentiel</span>
              <span className="font-mono text-[10px] text-muted-foreground">{validated}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Lint**
Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && npm run lint`
Expected: exit 0.

- [ ] **Step 3: Build**
Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && npm run build`
Expected: `✓ Compiled successfully`; the route list includes `/voyage/portrait`.

- [ ] **Step 4: Manual check — the gate and the print sheet**
1. With a voyage whose `portrait_status` is `draft`, open `/voyage/portrait`. Expect: « Votre portrait est rédigé et attend la validation de votre conseiller… » and a « Retour au voyage » button. No sections.
2. Have a counselor validate the portrait (phase 4, or flip `portrait_status` to `validated` directly in the DB for this check), then reload. Expect: the six sections in order — Phrase d'accroche, Qui tu es, Ce qui te fait vibrer, Ce dont tu as besoin, Les chemins possibles, Ce que ton portrait ne dit pas encore — on an A4-proportioned white sheet with a peach rule above the navy header.
3. Click « PDF ». Expect: the print preview shows the sheet with no AppBar and no action bar, and long sections flow onto page 2 instead of being cut.

- [ ] **Step 5: Commit**
```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add frontend/src/app/voyage/portrait/page.tsx
git commit -m "feat(voyage): the candidate portrait, validated only, printable

Reuses .report-shell and the existing print rules; the 409 body's status is
what decides which waiting message the person sees.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015fDz83zwALmXr4REGPGH8P"
```

---

### Task 8: App entry points — AppBar, `/analyse`, `/espace`

**Files:**
- Modify: `frontend/src/components/layout/AppBar.tsx:11` and `frontend/src/components/layout/AppBar.tsx:45-48`
- Modify: `frontend/src/app/analyse/page.tsx:1-6` and `frontend/src/app/analyse/page.tsx:57-59`
- Modify: `frontend/src/app/espace/page.tsx:3-20`, `frontend/src/app/espace/page.tsx:27-52`, `frontend/src/app/espace/page.tsx:78-79`
- Test: none (no frontend runner) — manual rows 12.20–12.22 land in Task 10

**Interfaces:**
- Consumes: `getVoyage` from `@/lib/voyage`; `Voyage` from `@/types/voyage`; `.voyage-rule`.
- Produces: no new exported symbols; three new links into `/voyage`.

- [ ] **Step 1: Add « Mon voyage » to the AppBar dropdown**
Replace `frontend/src/components/layout/AppBar.tsx:11`:
```tsx
import { ChevronDown, LogOut, LayoutDashboard, Map as MapIcon, PlusCircle, Shield } from "lucide-react"
```
Then insert this item directly after the « Mon espace » item that ends at `frontend/src/components/layout/AppBar.tsx:48`, before the `{user.role === "admin" && (` block at line 49:
```tsx
                <DropdownMenuItem render={<Link href="/voyage" />}>
                  <MapIcon />
                  Mon voyage
                </DropdownMenuItem>
```
`Map` is aliased because the bare name shadows the global `Map` constructor.

- [ ] **Step 2: Add the voyage card above the three parcours on `/analyse`**
Replace `frontend/src/app/analyse/page.tsx:4`:
```tsx
import { ArrowRight, Compass, Map as MapIcon, Sprout, Target } from "lucide-react"
```
Then insert this block between the header `</div>` at `frontend/src/app/analyse/page.tsx:57` and the `<div className="grid grid-cols-1 gap-5 md:grid-cols-3">` at line 59:
```tsx
        {/* The voyage is a fourth scenario, not a fourth parcours: full width
            and on the charter's inverted surface, so the difference reads
            before any hue does. The three parcours own orange, navy and teal. */}
        <Link
          href="/voyage"
          className="group mb-5 block overflow-hidden rounded-2xl bg-navy shadow-card transition-shadow hover:shadow-float focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-peach"
        >
          <span className="voyage-rule block" />
          <div className="flex flex-col gap-4 p-6 sm:flex-row sm:items-center">
            <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-white/10 text-peach">
              <MapIcon className="size-5" aria-hidden />
            </span>
            <div className="min-w-0 flex-1">
              <p className="eyebrow text-peach">Le voyage</p>
              <h2 className="mt-1 font-display text-lg font-bold text-white">
                Mon cahier d&apos;exploration
              </h2>
              <p className="mt-1 text-sm leading-relaxed text-white/80">
                5 minutes pour commencer. Ce qu&apos;il révèle enrichit toutes vos analyses.
              </p>
            </div>
            <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-white/10 px-3 py-1.5 text-xs font-medium text-white">
              Commencer
              <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-0.5" aria-hidden />
            </span>
          </div>
        </Link>

```

- [ ] **Step 3: Add the voyage status strip at the top of `/espace`**
Add to the import block at `frontend/src/app/espace/page.tsx:3-20`:
```tsx
import { getVoyage } from "@/lib/voyage"
import type { Voyage } from "@/types/voyage"
```
Add to the state block, directly after `const [origin, setOrigin] = useState("")` at `frontend/src/app/espace/page.tsx:32`:
```tsx
  const [voyage, setVoyage] = useState<Voyage | null>(null)
  const [voyageLoaded, setVoyageLoaded] = useState(false)
```
Add this effect directly after the analyses loader that ends at `frontend/src/app/espace/page.tsx:52`:
```tsx
  // The voyage is never required (spec decision 11) — this strip is an offer,
  // so a failed read renders nothing rather than an error.
  useEffect(() => {
    getVoyage()
      .then(setVoyage)
      .catch(() => {})
      .finally(() => setVoyageLoaded(true))
  }, [])
```
Then insert this block between the header `</div>` at `frontend/src/app/espace/page.tsx:78` and the `{loading ? (` at line 80:
```tsx
        {/* Le voyage — the fourth scenario, on the charter's inverted surface so
            it does not read as a fourth parcours card. */}
        {voyageLoaded && voyage && (
          <div className="mb-6 overflow-hidden rounded-2xl bg-navy shadow-card">
            <div className="voyage-rule" />
            <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center">
              <div className="min-w-0 flex-1">
                <p className="eyebrow text-peach">Le voyage</p>
                <p className="mt-1 font-display text-base font-bold text-white">
                  {voyage.sessions_completed.length} session
                  {voyage.sessions_completed.length > 1 ? "s" : ""} sur 6
                </p>
                {voyage.micro_phrase ? (
                  <p className="mt-1.5 line-clamp-2 text-sm italic text-white/80">
                    « {voyage.micro_phrase} »
                  </p>
                ) : null}
              </div>
              <Button
                render={
                  <Link
                    href={voyage.portrait_status === "validated" ? "/voyage/portrait" : "/voyage"}
                  />
                }
                size="lg"
                className="shrink-0 bg-white text-navy hover:bg-white/90"
              >
                {voyage.portrait_status === "validated" ? "Voir mon portrait" : "Continuer"}
                <ArrowRight />
              </Button>
            </div>
          </div>
        )}

        {voyageLoaded && !voyage && (
          <Link
            href="/voyage"
            className="group mb-6 block overflow-hidden rounded-2xl bg-navy shadow-card transition-shadow hover:shadow-float"
          >
            <span className="voyage-rule block" />
            <div className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center">
              <div className="min-w-0 flex-1">
                <p className="eyebrow text-peach">Le voyage</p>
                <p className="mt-1 font-display text-base font-bold text-white">
                  Six sessions pour poser ce que vous savez déjà de vous.
                </p>
                <p className="mt-1 text-sm text-white/80">
                  La première prend 5 minutes et se fait seul.
                </p>
              </div>
              <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-white/10 px-3 py-1.5 text-xs font-medium text-white">
                Commencer
                <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-0.5" aria-hidden />
              </span>
            </div>
          </Link>
        )}

```
`Link`, `Button` and `ArrowRight` are already imported by that file (`frontend/src/app/espace/page.tsx:4`, `:6`, `:19`).

- [ ] **Step 4: Lint**
Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && npm run lint`
Expected: exit 0.

- [ ] **Step 5: Build**
Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && npm run build`
Expected: `✓ Compiled successfully`.

- [ ] **Step 6: Manual check — the three app entry points**
1. Open `/analyse`. Expect: a full-width navy card with a peach rule reading « Le voyage · Mon cahier d'exploration » **above** the three white parcours cards, which are unchanged.
2. Open `/espace` with no voyage. Expect: a navy strip at the very top of the page, above the analyses grid, offering to start.
3. Create a voyage and finish session 0, then reopen `/espace`. Expect: the strip now reads « 1 session sur 6 » with the phrase in italics below it and a « Continuer » button.
4. Open the account dropdown in the top bar. Expect: « Mon espace », then « Mon voyage », then (as admin) « Administration », then « Déconnexion ». Click « Mon voyage » → lands on `/voyage`.

- [ ] **Step 7: Commit**
```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add frontend/src/components/layout/AppBar.tsx frontend/src/app/analyse/page.tsx frontend/src/app/espace/page.tsx
git commit -m "feat(voyage): three ways in — the chooser, the dashboard, the nav

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015fDz83zwALmXr4REGPGH8P"
```

---

### Task 9: The landing section

**Files:**
- Modify: `frontend/src/app/page.tsx:135` (new const after `PARCOURS`) and `frontend/src/app/page.tsx:231-233` (new section before `#parcours`)
- Test: none (no frontend runner) — manual row 12.23 lands in Task 10

**Interfaces:**
- Consumes: `Reveal`, `Button`, `Link`, `ArrowRight`, `Check`, `InfinityMark` — all already imported by that file (`frontend/src/app/page.tsx:1-14`).
- Produces: landing anchor `#voyage` linking to `/voyage`.

- [ ] **Step 1: Add the three-step constant**
The landing is a server component and cannot read the authed bank endpoint, so it must not restate the cahier's session titles — that would be the one duplication `frontend/src/types/voyage.ts` exists to avoid, and it would drift the day the bank is edited. It describes the **shape** of the voyage in the app's own vouvoiement instead.
Insert directly after the `PARCOURS` array closes at `frontend/src/app/page.tsx:135`:
```tsx
/* Le voyage — described by its shape, never by the cahier's session titles:
   this page is public and cannot read /api/voyage/bank, and restating the
   bank's French here is exactly the drift types/voyage.ts avoids. */
const VOYAGE_STEPS = [
  { n: "01", t: "Session 0, seul", d: "20 affirmations, 5 minutes. Vous repartez avec une phrase." },
  { n: "02", t: "Sessions 1 à 5, avec un conseiller", d: "Cinq séances courtes, ouvertes par le code de votre conseiller." },
  { n: "03", t: "Votre portrait", d: "Six sections, relues et validées par votre conseiller avant que vous les receviez." },
]
```

- [ ] **Step 2: Add the section above the three scenario cards**
Insert between the hero's closing `</section>` at `frontend/src/app/page.tsx:231` and the `{/* ───── Choose your scenario ───── */}` comment at line 233:
```tsx
      {/* ───────────────────── Le voyage ───────────────────── */}
      <section id="voyage" className="mx-auto max-w-6xl px-5 pt-16 sm:px-8 lg:pt-20">
        <Reveal>
          <div className="overflow-hidden rounded-3xl bg-navy shadow-float">
            <div className="voyage-rule" />
            <div className="grid gap-8 p-8 sm:p-10 lg:grid-cols-[1.05fr_0.95fr] lg:items-center">
              <div>
                <p className="eyebrow inline-flex items-center gap-2 text-peach">
                  <InfinityMark className="text-[1.05em]" /> Le voyage
                </p>
                <h2 className="mt-4 font-display text-3xl font-bold text-white sm:text-4xl">
                  Avant de parler de poste, parlons de vous.
                </h2>
                <p className="mt-4 max-w-[34rem] leading-relaxed text-white/80">
                  Six sessions courtes pour poser ce que vous savez déjà de vous : ce qui vous met
                  en mouvement, le cadre où vous travaillez bien, ce que vous ne voulez plus.
                  Ce que vous y répondez enrichit ensuite chacune de vos analyses.
                </p>
                <div className="mt-7">
                  <Button
                    render={<Link href="/voyage" />}
                    size="xl"
                    className="bg-white text-navy hover:bg-white/90"
                  >
                    Commencer le voyage <ArrowRight />
                  </Button>
                </div>
                <ul className="mt-7 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-white/70">
                  {[
                    "5 minutes pour la première session",
                    "Vos réponses sont chiffrées",
                    "Supprimables à tout moment",
                  ].map((t) => (
                    <li key={t} className="inline-flex items-center gap-1.5">
                      <Check className="size-4 text-peach" /> {t}
                    </li>
                  ))}
                </ul>
              </div>

              <ul className="space-y-2.5">
                {VOYAGE_STEPS.map((s) => (
                  <li key={s.n} className="flex gap-3 rounded-xl bg-white/5 px-4 py-3.5">
                    <span className="mt-0.5 font-mono text-xs font-bold text-peach">{s.n}</span>
                    <span className="min-w-0">
                      <span className="block text-sm font-semibold text-white">{s.t}</span>
                      <span className="mt-0.5 block text-xs leading-relaxed text-white/70">{s.d}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </Reveal>
      </section>

```

- [ ] **Step 3: Lint**
Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && npm run lint`
Expected: exit 0.

- [ ] **Step 4: Build**
Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && npm run build`
Expected: `✓ Compiled successfully`; `/` still prerenders as static.

- [ ] **Step 5: Manual check — the landing**
1. Open `/` logged out and scroll past the hero. Expect: a navy band with a peach rule reading « Le voyage · Avant de parler de poste, parlons de vous. », a three-step list, and a white « Commencer le voyage » button — **above** « Trois situations, trois lectures ».
2. Click « Commencer le voyage » while logged out. Expect: redirected to `/connexion?redirect=/voyage`; after logging in you land on `/voyage`.
3. Read the whole section aloud. Expect: no « boussole », « copilote », « miroir », « révélation », « épanouissement », « alignement », « excellence », « talent unique », « vous vous démarquez », and no tutoiement anywhere in it.

- [ ] **Step 6: Commit**
```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add frontend/src/app/page.tsx
git commit -m "feat(voyage): a landing section above the three scenarios

Described by its shape, not by the cahier's session titles — the landing is
public and cannot read the bank, and restating its French would drift.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015fDz83zwALmXr4REGPGH8P"
```

---

### Task 10: Manual test plan and full verification

**Files:**
- Modify: `TEST-PLAN.md:211-212` (insert a new section between « § 11 · Security spot-check » and « ## What to report back »)
- Test: `cd backend && pytest` (whole suite) and `cd frontend && npm run lint && npm run build`

**Interfaces:**
- Consumes: everything Tasks 1–9 produced.
- Produces: `TEST-PLAN.md` « § 12 · Le voyage » — the PM-facing pass for this phase.

- [ ] **Step 1: Add « § 12 · Le voyage » to `TEST-PLAN.md`**
Section numbers 10 and 11 are already taken in that file (`## 10 · Print / PDF` at `TEST-PLAN.md:193`, `## 11 · Security spot-check` at `:204`), so the voyage is § 12. The row format is the file's own: a `| # | Do | Expect |` table with a `|---|---|---|` separator, sub-sections as `### N.M Title`, and a `>` blockquote for a rule the PM cares about.
Insert between the `---` at `TEST-PLAN.md:211` and `## What to report back` at `TEST-PLAN.md:213`:
```markdown
## 12 · Le voyage

**You need to be logged in.** Sessions 1 to 5 additionally need a counselor code
and a Profil de base with at least a prénom and a tranche d'âge — that is the
gate, not a bug.

The text inside the sessions and inside the portrait is the paper cahier,
reproduced word for word, and it says *tu*. Everything around it — buttons,
cards, the top bar, error messages — says *vous*. If you find a *tu* on a
button or a *vous* inside a session, that is a bug.

### 12.1 Entry points

| # | Do | Expect |
|---|---|---|
| 12.1.1 | Open the landing page and scroll past the hero | A navy band, « Le voyage — Avant de parler de poste, parlons de vous », **above** the three scenario cards |
| 12.1.2 | Click "Commencer le voyage" while logged out | `/connexion?redirect=/voyage`, and after logging in you land on `/voyage` |
| 12.1.3 | Open `/analyse` | A full-width navy card "Le voyage · Mon cahier d'exploration" **above** the three parcours cards. The three cards themselves are unchanged |
| 12.1.4 | Open `/espace` with no voyage started | A navy strip at the very top offering to start. It never blocks the analyses below it |
| 12.1.5 | Open the account dropdown in the top bar | "Mon espace", then **"Mon voyage"**, then "Déconnexion" (plus "Administration" if you are admin) |
| 12.1.6 | Log out and open `/voyage` directly | Bounced to `/connexion?redirect=/voyage`. You should never see the consent form logged out |

### 12.2 Consent and the age gate

| # | Do | Expect |
|---|---|---|
| 12.2.1 | Open `/voyage` for the first time | Two checkboxes: a consent line about encrypted answers, and "J'ai 15 ans ou plus" |
| 12.2.2 | Leave both unticked | "Commencer le voyage" is **greyed out and unclickable** |
| 12.2.3 | Tick only the age box | Still greyed out — both are required |
| 12.2.4 | Tick both, click the button | The six session rows appear |
| 12.2.5 | Read the intro | It says in as many words that no session is required and that your analyses work without one |

### 12.3 Locked sessions

| # | Do | Expect |
|---|---|---|
| 12.3.1 | Look at rows 1 to 5 with no counselor code | Each shows a grey pill reading **"Avec un conseiller"**. There is **no button at all** — not a greyed-out one |
| 12.3.2 | Enter a valid counselor code, click "Activer" | The code field disappears; the rows now read **"Complétez votre profil"** if your profile is empty |
| 12.3.3 | Fill prénom + tranche d'âge at `/profil`, return to `/voyage` | Row 1 offers "Commencer"; rows 2 to 5 read **"Terminez la session précédente"** |
| 12.3.4 | Enter a wrong or disabled code | "Code invalide ou désactivé." in red. Nothing else changes |
| 12.3.5 | Go to `/voyage/session/4` by typing the URL, with session 3 unfinished | A lock screen with the reason and a "Retour au voyage" button. No questions, no dead "Suivant" |

### 12.4 Session 0 — the 5-minute one

| # | Do | Expect |
|---|---|---|
| 12.4.1 | Click "Commencer" on session 0 | One scrolling list of **20** affirmations, each with a ✓ and a ✗ button. Not one question per screen |
| 12.4.2 | Answer five rows, then reload the page | The five answers are still there — each row saves the moment you press it |
| 12.4.3 | Answer all 20, click "Suivant" | The billet de sortie: two free-text boxes, marked facultatif |
| 12.4.4 | Click "Terminer" with the billet empty | Accepted. Back on `/voyage`, session 0 stamped with a check |
| 12.4.5 | Watch the top of the hub | "Votre phrase" shows a spinner, then a single sentence a few seconds later. No page reload needed |
| 12.4.6 | Read that sentence | One sentence about you. **No number, no score, no percentage, no jargon word.** If you see any of those, that is the bug this whole feature is built to avoid |
| 12.4.7 | Reopen `/voyage/session/0` | It opens in read-only: a banner says the session is finished, the ✓ / ✗ buttons are inert, and the last button says "Retour au voyage" |

### 12.5 Sessions 1 to 5 — the player

| # | Do | Expect |
|---|---|---|
| 12.5.1 | Open session 1 | The session's own intro paragraphs, then **one scene per screen** |
| 12.5.2 | Read a scene | A title, a short story, a question, then 6 lettered options (session 1 scene 6 has 8) |
| 12.5.3 | Click "Suivant" without choosing | "Choisissez une réponse pour continuer." The screen does not advance |
| 12.5.4 | Answer scenes 1 and 2, close the tab mid-scene 3, reopen the session | It lands on **scene 3**, with 1 and 2 already answered |
| 12.5.5 | Answer a scene, then turn off your network, then click "Suivant" | An error appears and the screen does not advance. Turn the network back on, click again — it saves and moves on. You lose at most the current scene |
| 12.5.6 | Click "Précédent" | Back one scene, answer still selected. No re-save needed |
| 12.5.7 | Reach the last screen of a session | The session's closing paragraphs, then the billet de sortie for that session |
| 12.5.8 | Finish sessions 1 to 5 | After "Terminer" on session 5 the hub shows all six stamped, and a line saying the portrait is awaiting your counselor's validation |

### 12.6 The portrait

| # | Do | Expect |
|---|---|---|
| 12.6.1 | Open `/voyage/portrait` before the counselor validates | "Votre portrait est rédigé et attend la validation de votre conseiller." No sections are shown |
| 12.6.2 | Have the counselor validate it, then reload | Six sections in this order: Phrase d'accroche · Qui tu es · Ce qui te fait vibrer · Ce dont tu as besoin · Les chemins possibles · Ce que ton portrait ne dit pas encore |
| 12.6.3 | Read the whole portrait | Prose, tutoiement, **no score, no percentage, no named framework, no "tu es…" verdict, no named métier** |
| 12.6.4 | Click "PDF" | Print preview: an A4 sheet with no top bar and no buttons, long sections flowing onto page 2 |
| 12.6.5 | Go back to `/espace` | The voyage strip now says "Voir mon portrait" |

### 12.7 Erasure

| # | Do | Expect |
|---|---|---|
| 12.7.1 | On `/voyage`, click "Supprimer mon voyage" | A confirmation naming exactly what goes: réponses, phrase, portrait |
| 12.7.2 | Confirm | Back to the consent screen, as if you had never started |
| 12.7.3 | Open `/profil` | **Untouched.** Deleting the voyage must not touch the Profil de base, and deleting the profile must not touch the voyage |

> The rule the PM cares about here: **the person never sees a score, a trait
> name, or a framework name.** Not on the hub, not in the phrase, not in the
> portrait. Everything numeric stays on the counselor's side of the wall.
> If a number or a jargon word reaches any of these screens, report it first.

---
```

- [ ] **Step 2: Run the full backend suite**
Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/backend && ./venv/bin/python -m pytest`
Expected: exit 0, `N passed`, no failures and no collection errors. Two things specifically:
- `tests/test_voyage_parity.py` is **green** — the three lock strings and the six `PORTRAIT_SECTIONS` entries in `frontend/src/types/voyage.ts` match `backend/app/models/voyage.py` and `backend/app/services/voyage/generation.py`.
- The baseline before the voyage work was **145 passed** (`145 passed, 59 warnings`); N is that number plus everything phases 0–2 added. This phase adds no Python, so N must not go **down**.

- [ ] **Step 3: Run the frontend lint**
Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && npm run lint`
Expected: exit 0, no errors. `react/no-unescaped-entities` is the one to watch — every apostrophe in JSX text must be `&apos;`.

- [ ] **Step 4: Run the frontend build**
Run: `cd /Users/imran/Downloads/design_handoff_cv_analyzer/frontend && npm run build`
Expected: `✓ Compiled successfully`, no TypeScript errors, and the route table listing `/voyage`, `/voyage/session/[n]` and `/voyage/portrait` alongside the existing routes.

- [ ] **Step 5: Walk § 12 end to end once**
Run through `TEST-PLAN.md` § 12.1 to § 12.7 against http://localhost:8080 with a fresh candidate account and a live counselor code. Every row must match. Anything that does not is a defect in this phase, not a note for the PM — fix it and re-run steps 2 to 4 before committing.

- [ ] **Step 6: Commit**
```bash
cd /Users/imran/Downloads/design_handoff_cv_analyzer
git add TEST-PLAN.md
git commit -m "docs(voyage): the manual pass for the candidate side

Section 12 — 10 and 11 are already taken by Print/PDF and the security
spot-check.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_015fDz83zwALmXr4REGPGH8P"
```

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
  /** Present on an error row (phase-2 commit c9edd16) — contract § E:1185 is
   *  stale on this point. */
  error?: string | null
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
  /** The candidate has already read this, unreviewed — the counselor sheet
   *  must render it as AI-written text, not as ordinary prose (binding
   *  requirement, docs/superpowers/plans/2026-09-09-voyage-phase-4-counselor-ui.md,
   *  Task 5). */
  micro_phrase: string | null
  micro_status: MicroStatus
  /** The row's own scoring version — synthesis.scoring_version is always the
   *  bank's current value, so this is the only way to detect a drifted row. */
  scoring_version: string
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
  // Trimmed exactly as session_lock() trims in Python — a whitespace-only
  // prenom or tranche_age is treated as absent.
  if (!(profile?.prenom ?? "").trim() || !(profile?.tranche_age ?? "").trim()) return LOCK_PROFILE
  const previous = String(Number(n) - 1)
  if (!(voyage.sessions_completed as string[]).includes(previous)) return LOCK_ORDER
  return null
}

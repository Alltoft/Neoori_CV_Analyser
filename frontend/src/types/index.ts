export interface User {
  id: string
  email: string
  role: "candidate" | "counselor" | "admin"
  plan: "free" | "paid"
  credits_remaining: number
  created_at: string
}

/** Parcours id. Legacy rows carry "A"/"B"; the backend normalises them. */
export type Parcours = "1" | "2" | "3"

/** Superset accepted on the wire, so legacy analyses still type-check. */
export type AnalysisPath = Parcours | "A" | "B"

/**
 * Coerce a stored `_path` to a parcours id. Analyses written before the v1.2
 * migration carry "A"/"B"; the backend normalises the same way on read.
 */
export function normalizeParcours(raw: string | undefined | null): Parcours {
  if (raw === "A") return "1"
  if (raw === "B") return "3"
  return raw === "1" || raw === "2" || raw === "3" ? raw : "1"
}

export type SubProfile = "b1" | "b2" | "b3"

/**
 * Render instructions for one report section, supplied by the backend in
 * registry order. The client must never sort output keys itself — parcours 2
 * uses letter keys and parcours 3 Roman numerals, and `Number("A")` is NaN,
 * which leaves Array.sort in insertion order without raising.
 */
export interface SectionMeta {
  key: string
  title: string
  render: "markdown" | "tags"
  tiers: string[]
}

export interface AnalysisInputs {
  // Chemin A
  cv_text?: string
  cible_visee?: string
  prenom?: string
  tranche_age?: string
  localisation?: string
  situation_actuelle?: string
  type_mobilite?: string | string[]
  notes_specifiques?: string
  // Chemin B
  nom?: string
  aime?: string[]
  competent?: string[]
  refuse?: string[]
  pause_activite?: string
  contraintes_pratiques?: string[]
  contraintes_b3?: string[]
  accompagnement?: string
  cv_b3?: string
  // Discriminators (echoed from backend)
  _path?: AnalysisPath
  _sub_profile?: SubProfile
  /** Plan the analysis was generated on. "haiku"/"sonnet" on rows written
   *  before the plan-name migration — see backend services/tiers.py. */
  _tier?: "free" | "paid" | "premium" | "haiku" | "sonnet"
}

export interface AnalysisInputsB {
  _path: "B"
  _sub_profile: SubProfile
  nom: string
  aime: string[]
  competent: string[]
  refuse?: string[]
  pause_activite?: string
  contraintes_pratiques?: string[]
  contraintes_b3?: string[]
  accompagnement?: string
  cv_b3?: string
}

export interface AnalysisSection {
  title: string
  body_markdown: string
  items: AnalysisSectionItem[]
}

export interface AnalysisSectionItem {
  trait?: string
  condition_of_expression?: string
  fact?: string
  target_relevance?: string
  [key: string]: string | undefined
}

export type AnalysisOutput = Record<string, AnalysisSection>

export type AnalysisStatus = "draft" | "queued" | "running" | "success" | "error" | "timeout"

export interface Analysis {
  id: string
  status: AnalysisStatus
  inputs: AnalysisInputs | null
  output: AnalysisOutput | null
  /** Ordered render instructions. Absent on responses from an older backend. */
  sections_meta?: SectionMeta[]
  /** Section keys the counselor synthesis shows, for this parcours. */
  counselor_keys?: string[]
  /** "code" | "payment" once unlocked, null while on the free tier. */
  unlock_method?: string | null
  share_token: string | null
  prompt_version_id: string | null
  tokens_in: number | null
  tokens_out: number | null
  /** 0-99 while the generation streams, 100 once it succeeds. Read off the
   *  stream itself, so the waiting screen reports the run rather than a clock.
   *  Absent on responses from an older backend. */
  progress?: number
  created_at: string
  completed_at: string | null
}

export interface PromptVersion {
  id: string
  version_label: string
  system_prompt_text?: string
  is_active: boolean
  path?: AnalysisPath
  author: string | null
  created_at: string
}

export interface CounselorNote {
  id: string
  analysis_id: string
  body: string | null
  updated_at: string
}

// Section membership now comes from `Analysis.sections_meta` (backend
// registry order). The constants below survive only for the parcours-1
// pricing copy on /debloquer, which Phase 3 rebuilds around the 3 tiers.
export const PAID_SECTIONS = ["5", "6", "7", "8", "9"] as const

export const SECTION_TITLES: Record<string, string> = {
  "1": "Lecture stratégique du parcours",
  "2": "Forces du profil pour la cible",
  "3": "Compétences transférables",
  "4": "Ce qui reste à renforcer",
  "5": "Préconisations terrain",
  "6": "Exemple de réécriture",
  "7": "Synthèse pour le candidat",
  "8": "Pistes d'évolution",
  "9": "Proposition de CV retravaillé",
}


export const MOBILITY_OPTIONS = [
  "évolution",
  "reconversion proche",
  "reconversion forte",
  "première insertion",
  "retour à l'emploi",
] as const

export const AGE_BRACKETS = ["< 25", "25–34", "35–44", "45–54", "55+"] as const

export const SITUATION_OPTIONS = [
  "1ère insertion pro",
  "en poste",
  "en recherche",
  "en formation",
  "en pause",
] as const

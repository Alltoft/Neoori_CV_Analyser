export interface User {
  id: string
  email: string
  role: "candidate" | "counselor" | "admin"
  plan: "free" | "paid"
  credits_remaining: number
  created_at: string
}

export type AnalysisPath = "A" | "B"
export type SubProfile = "b1" | "b2" | "b3"

export interface AnalysisInputs {
  // Chemin A
  cv_text?: string
  cible_visee?: string
  prenom?: string
  tranche_age?: string
  localisation?: string
  situation_actuelle?: string
  type_mobilite?: string
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
  _tier?: "haiku" | "sonnet"
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
  share_token: string | null
  prompt_version_id: string | null
  tokens_in: number | null
  tokens_out: number | null
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

export const FREE_SECTIONS = ["1", "2", "3", "4"] as const
export const PAID_SECTIONS = ["5", "6", "7", "8", "9"] as const
export const COUNSELOR_SECTIONS = ["1", "4", "5"] as const

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

export const COUNSELOR_SECTIONS_B = ["1", "2", "8"] as const

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

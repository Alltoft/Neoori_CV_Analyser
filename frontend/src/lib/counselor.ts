import { api } from "./api"
import type {
  Analysis, Beneficiaire, CounselorAnalysisRow, CounselorApplication, CounselorCodeRow,
  CounselorProfile, CounselorStats, DomaineActivite, TypeStructure, User,
} from "@/types"

export interface ApplyPayload {
  // Votre structure
  structure: string
  type_structure: TypeStructure
  /** Required only when type_structure is "autre". */
  type_structure_autre?: string
  /** 14 digits; optional only for an indépendant, checked if given anyway. */
  siret?: string
  adresse_rue: string
  adresse_code_postal: string
  adresse_ville: string
  domaines: DomaineActivite[]
  // Vous
  nom_complet: string
  fonction: string
  telephone: string
  // Validation — two separate ticks
  consent: boolean
  consent_donnees: boolean
  /** Omitted when an already-signed-in candidate applies from their espace. */
  email?: string
  password?: string
}

/** The conseiller's own surface: /api/counselor. The token-addressed share link
 *  that /api/c served is retired (four-doors spec, decision 43). */
export const counselor = {
  apply: (payload: ApplyPayload) =>
    api.post<{ user: User; profile: CounselorProfile; mail_sent?: boolean }>("/counselor/apply", payload),

  /** Readable while pending, rejected or revoked — it is the state switch. */
  me: () =>
    api.get<{ profile: CounselorProfile | null }>("/counselor/me", { skipRedirect: true }),

  stats: () => api.get<CounselorStats>("/counselor/stats"),

  codes: () => api.get<{ codes: CounselorCodeRow[] }>("/counselor/codes"),

  createCode: (label: string, maxUses?: number) =>
    api.post<{ code: CounselorCodeRow }>("/counselor/codes", { label, max_uses: maxUses }),

  revokeCode: (id: string) => api.delete<{ code: CounselorCodeRow }>(`/counselor/codes/${id}`),

  beneficiaires: () => api.get<{ beneficiaires: Beneficiaire[] }>("/counselor/beneficiaires"),

  /** Advisor-door reports — the counselor's alone (four-doors spec, ruling 2). */
  analyses: () => api.get<{ analyses: CounselorAnalysisRow[] }>("/counselor/analyses"),
  analysis: (id: string) =>
    api.get<{ analysis: Analysis; code_label: string | null }>(`/counselor/analyses/${id}`),
  deleteAnalysis: (id: string) => api.delete(`/counselor/analyses/${id}`),
  relaunch: (id: string) => api.post<{ analysis: Analysis }>(`/counselor/analyses/${id}/relaunch`),
  note: (id: string) => api.get<{ note: string }>(`/counselor/analyses/${id}/notes`),
  saveNote: (id: string, note: string) =>
    api.put<{ note: string }>(`/counselor/analyses/${id}/notes`, { note }),
}

export const adminCounselor = {
  list: (status?: string) =>
    api.get<{ applications: CounselorApplication[] }>(
      `/admin/counselor-applications${status ? `?status=${status}` : ""}`,
    ),

  approve: (id: string, maxCodes: number | null, maxUsesPerCode: number | null) =>
    api.post<{ application: CounselorApplication }>(
      `/admin/counselor-applications/${id}/approve`,
      { max_codes: maxCodes, max_uses_per_code: maxUsesPerCode },
    ),

  reject: (id: string, reason: string) =>
    api.post<{ application: CounselorApplication }>(
      `/admin/counselor-applications/${id}/reject`, { reason },
    ),

  revoke: (id: string, reason: string) =>
    api.post<{ application: CounselorApplication }>(
      `/admin/counselor-applications/${id}/revoke`, { reason },
    ),

  limits: (id: string, maxCodes: number | null, maxUsesPerCode: number | null) =>
    api.put<{ application: CounselorApplication }>(
      `/admin/counselor-applications/${id}/limits`,
      { max_codes: maxCodes, max_uses_per_code: maxUsesPerCode },
    ),
}

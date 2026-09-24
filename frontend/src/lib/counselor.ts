import { api } from "./api"
import type {
  Beneficiaire, CounselorApplication, CounselorCodeRow,
  CounselorProfile, CounselorStats, User,
} from "@/types"

export interface ApplyPayload {
  structure: string
  fonction: string
  telephone: string
  email_pro?: string
  message?: string
  consent: boolean
  /** Omitted when an already-signed-in candidate applies from their espace. */
  email?: string
  password?: string
}

/** The conseiller's own surface. /api/counselor, not /api/c — that one is the
 *  token-addressed share link for an analysis and has no account behind it. */
export const counselor = {
  apply: (payload: ApplyPayload) =>
    api.post<{ user: User; profile: CounselorProfile }>("/counselor/apply", payload),

  /** Readable while pending, rejected or revoked — it is the state switch. */
  me: () =>
    api.get<{ profile: CounselorProfile | null }>("/counselor/me", { skipRedirect: true }),

  stats: () => api.get<CounselorStats>("/counselor/stats"),

  codes: () => api.get<{ codes: CounselorCodeRow[] }>("/counselor/codes"),

  createCode: (label: string, maxUses?: number) =>
    api.post<{ code: CounselorCodeRow }>("/counselor/codes", { label, max_uses: maxUses }),

  revokeCode: (id: string) => api.delete<{ code: CounselorCodeRow }>(`/counselor/codes/${id}`),

  beneficiaires: () => api.get<{ beneficiaires: Beneficiaire[] }>("/counselor/beneficiaires"),
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

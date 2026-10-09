import { api } from "./api"
import type { Analysis, AnalysisInputs } from "@/types"

export type FormInputs = Pick<AnalysisInputs, "cv_text" | "cible_visee" | "_chemin">

/** A no-login report's key lives in the URL fragment (four-doors spec,
 *  decision 30): a fragment is never sent to a server and never appears in
 *  a Referer. */
export function tokenFromHash(): string | null {
  const token = window.location.hash.replace(/^#/, "")
  return token || null
}

/** The signed-out draft and the no-login report. The draft's key never
 *  reaches this code: it lives in an HttpOnly cookie the server sets. */
export const held = {
  saveDraft: (inputs: FormInputs) =>
    api.post<{ analysis: Analysis }>("/analyses/draft", { inputs }, { skipRedirect: true }),
  get: () => api.get<{ analysis: Analysis }>("/analyses/held", { skipRedirect: true }),
  claim: () => api.post<{ analysis: Analysis }>("/analyses/claim", undefined, { skipRedirect: true }),
  hold: (token: string) => api.post<Record<string, never>>("/analyses/hold", undefined, { token, skipRedirect: true }),
  byToken: (token: string) =>
    api.get<{ analysis: Analysis }>("/analyses/by-token", { token, skipRedirect: true }),
  remove: (id: string, token: string) => api.delete(`/analyses/${id}`, { token, skipRedirect: true }),
}

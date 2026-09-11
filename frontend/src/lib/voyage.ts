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

/** Retry a session-0 phrase stuck in `error`, or stalled in `generating`
 *  (backend/app/routes/voyage.py MICRO_RETRY_STALE_MINUTES). 202 with the
 *  updated voyage; 404/409 surface through ApiError as usual. */
export const retryMicro = (): Promise<Voyage> =>
  api.post<{ voyage: Voyage }>("/voyage/micro/retry").then((r) => r.voyage)

/** 200 only when portrait_status == "validated"; otherwise the server answers
 *  409 with {error, status} — read the status with errorStatus(). With no
 *  voyage at all the server answers 404 {error} with no status; errorStatus()
 *  then returns null and the caller falls back to the message. */
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

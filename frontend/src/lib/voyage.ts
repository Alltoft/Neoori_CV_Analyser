/**
 * Le voyage — typed wrappers over /api/voyage.
 *
 * Mirrors backend/app/routes/voyage.py § E. The only module in the frontend
 * that knows a voyage endpoint path — phase 4 (ruling R9) adds the counselor
 * calls (/c/<token> and friends) so /voyage/c/[token]/page.tsx never spells
 * out a raw path either.
 */
import { ApiError, api } from "@/lib/api"
import type {
  Bank, BankResponse, CandidatePortrait, CandidatePortraitResponse,
  CounselorPortrait, CounselorPortraitResponse, CounselorVoyage, CounselorVoyageResponse,
  PortraitSections, ResponsesResponse, SessionId, Voyage, VoyageNote, VoyageNoteResponse,
  VoyageResponse, VoyageResponses,
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

// ── counselor (GET /api/voyage/c/<token> and friends) ────────────────────────
// Role AND token required server-side (spec § Security) — /voyage/c/[token]
// never calls these unless the signed-in user is already counselor/admin.

/** The page-18 sheet plus the portrait draft, recomputed from the answers on
 *  every read (contracts § E10 — ten keys, phase-4 ruling R10's
 *  scoring_version included). 404 when the token matches no voyage. */
export const getCounselorVoyage = (token: string): Promise<CounselorVoyage> =>
  api.get<CounselorVoyageResponse>(`/voyage/c/${token}`).then((r) => r.voyage)

/** Replace all six sections. 200 with edited:true while draft or validated;
 *  409 "Aucun portrait à modifier." while generating or error; a blank,
 *  missing or unknown key is a 400 {"errors": [...]} (§ E11). */
export const putPortrait = (
  token: string,
  sections: PortraitSections,
): Promise<CounselorPortrait> =>
  api.put<CounselorPortraitResponse>(`/voyage/c/${token}/portrait`, { sections })
    .then((r) => r.portrait)

/** 202 while draft or error, or while generating past
 *  PORTRAIT_RETRY_STALE_MINUTES (10 min); 409 otherwise — a fresh generating
 *  row, a validated one, or no portrait at all (§ E12). */
export const regeneratePortrait = (token: string): Promise<CounselorPortrait> =>
  api.post<CounselorPortraitResponse>(`/voyage/c/${token}/portrait/regenerate`, {})
    .then((r) => r.portrait)

/** « Valider et transmettre ». 200 only while draft — the server validates
 *  the STORED sections, so a caller must save first (phase-4 ruling R12);
 *  409 otherwise (§ E13). */
export const validatePortrait = (token: string): Promise<CounselorPortrait> =>
  api.post<CounselorPortraitResponse>(`/voyage/c/${token}/validate`, {})
    .then((r) => r.portrait)

/** This counselor's own note on this voyage — never the candidate's, never
 *  another counselor's (contracts § C.7). A miss is 200 {note: null}, not a
 *  rejection (§ E14). */
export const getNote = (token: string): Promise<VoyageNote | null> =>
  api.get<VoyageNoteResponse>(`/voyage/c/${token}/notes`).then((r) => r.note)

/** Upsert, keyed on (voyage, counselor). body: "" legitimately clears the
 *  note (200); an absent or null body is refused with 400 "Note invalide."
 *  server-side (§ E15) — never send those, this wrapper always sends a
 *  string. */
export const putNote = (token: string, body: string): Promise<VoyageNote | null> =>
  api.put<VoyageNoteResponse>(`/voyage/c/${token}/notes`, { body }).then((r) => r.note)

/* Central FR localization for backend enum values — so no raw English token
   (success / paid / counselor …) ever leaks into the UI. Use these everywhere. */

export type AnalysisStatus =
  | "queued" | "running" | "success" | "error" | "timeout" | "draft" | string

export const STATUS_LABELS: Record<string, string> = {
  queued: "en file",
  running: "en cours",
  success: "terminée",
  error: "échec",
  timeout: "expirée",
  draft: "brouillon",
}

export type StatusTone = "success" | "warning" | "danger" | "info" | "neutral"

export const STATUS_TONES: Record<string, StatusTone> = {
  queued: "info",
  running: "info",
  success: "success",
  error: "danger",
  timeout: "warning",
  draft: "neutral",
}

export const statusLabel = (s?: string) => (s ? STATUS_LABELS[s] ?? s : "—")
export const statusTone = (s?: string): StatusTone => (s ? STATUS_TONES[s] ?? "neutral" : "neutral")

export const ROLE_LABELS: Record<string, string> = {
  candidate: "candidat",
  counselor: "conseiller",
  admin: "administrateur",
}
export const roleLabel = (r?: string) => (r && ROLE_LABELS[r]) ?? r ?? "—"

export const PLAN_LABELS: Record<string, string> = {
  free: "gratuit",
  paid: "payant",
}
export const planLabel = (p?: string) => (p && PLAN_LABELS[p]) ?? p ?? "—"

/* Compact French number / token formatting */
const nf = new Intl.NumberFormat("fr-FR")
export const fmtInt = (n?: number | null) => (n == null ? "—" : nf.format(n))
export const fmtCompact = (n?: number | null) =>
  n == null ? "—" : new Intl.NumberFormat("fr-FR", { notation: "compact", maximumFractionDigits: 1 }).format(n)
export const fmtEur = (n?: number | null) =>
  n == null ? "—" : new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR" }).format(n)
export const fmtPct = (n?: number | null, digits = 0) =>
  n == null ? "—" : `${n.toFixed(digits).replace(".", ",")} %`

export const fmtDate = (d?: string | null) => {
  if (!d) return "—"
  const date = new Date(d)
  return isNaN(+date) ? "—" : date.toLocaleDateString("fr-FR", { day: "2-digit", month: "short", year: "numeric" })
}
export const fmtDateTime = (d?: string | null) => {
  if (!d) return "—"
  const date = new Date(d)
  return isNaN(+date)
    ? "—"
    : date.toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" })
}

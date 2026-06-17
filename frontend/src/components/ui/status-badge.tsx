import { Badge } from "./badge"
import { statusLabel, statusTone, type StatusTone } from "@/lib/format"

const TONE_VARIANT: Record<StatusTone, "success" | "warning" | "destructive" | "info" | "secondary"> = {
  success: "success",
  warning: "warning",
  danger: "destructive",
  info: "info",
  neutral: "secondary",
}

/** Localized, color-coded analysis status pill (success/error/timeout/running/draft). */
export function StatusBadge({ status, className }: { status?: string; className?: string }) {
  return (
    <Badge variant={TONE_VARIANT[statusTone(status)]} className={className}>
      {statusLabel(status)}
    </Badge>
  )
}

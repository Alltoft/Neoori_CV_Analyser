import * as React from "react"
import { cn } from "@/lib/utils"

/** Compact KPI tile used across the admin dashboards. */
export function StatCard({
  label,
  value,
  hint,
  icon,
  accent = false,
  className,
}: {
  label: React.ReactNode
  value: React.ReactNode
  hint?: React.ReactNode
  icon?: React.ReactNode
  accent?: boolean
  className?: string
}) {
  return (
    <div
      className={cn(
        "rounded-xl bg-card p-4 ring-1 ring-foreground/10 shadow-soft",
        accent && "bg-navy text-white ring-0",
        className,
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <p className={cn("eyebrow", accent ? "text-peach" : "text-muted-foreground")}>{label}</p>
        {icon && <span className={cn(accent ? "text-peach" : "text-orange")}>{icon}</span>}
      </div>
      <p className={cn("mt-2 font-display text-2xl font-bold tabular-nums", accent ? "text-white" : "text-navy")}>
        {value}
      </p>
      {hint && (
        <p className={cn("mt-0.5 text-xs", accent ? "text-white/65" : "text-muted-foreground")}>{hint}</p>
      )}
    </div>
  )
}

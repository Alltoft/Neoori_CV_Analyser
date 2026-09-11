"use client"

import { Check, X } from "lucide-react"

import { cn } from "@/lib/utils"

/**
 * One session-0 affirmation with its OUI / NON pair.
 *
 * Two buttons rather than one checkbox: the cahier prints two boxes, and the
 * completion endpoint refuses a session that still has an unanswered item, so
 * "not answered yet" has to be a state the person can see.
 */
export function ChecklistRow({
  n,
  text,
  value,
  disabled,
  onChange,
}: {
  n: number
  text: string
  value: boolean | undefined
  disabled?: boolean
  onChange: (next: boolean) => void
}) {
  return (
    <div
      className={cn(
        "flex items-center gap-3 rounded-xl px-3 py-2.5 ring-1 transition-colors",
        value === undefined
          ? "bg-secondary/60 ring-foreground/5"
          : "bg-card ring-foreground/10",
      )}
    >
      <span className="w-5 shrink-0 font-mono text-[11px] text-muted-foreground">{n}</span>
      <p className="min-w-0 flex-1 text-sm leading-snug text-navy">{text}</p>

      <div className="flex shrink-0 gap-1.5">
        <button
          type="button"
          disabled={disabled}
          aria-pressed={value === true}
          aria-label={`Oui — ${text}`}
          onClick={() => onChange(true)}
          className={cn(
            "grid size-9 place-items-center rounded-lg border transition-colors disabled:cursor-not-allowed disabled:opacity-50",
            value === true
              ? "border-success bg-success text-white"
              : "border-input text-muted-foreground hover:border-success/60 hover:text-success",
          )}
        >
          <Check className="size-4" aria-hidden />
        </button>

        <button
          type="button"
          disabled={disabled}
          aria-pressed={value === false}
          aria-label={`Non — ${text}`}
          onClick={() => onChange(false)}
          className={cn(
            "grid size-9 place-items-center rounded-lg border transition-colors disabled:cursor-not-allowed disabled:opacity-50",
            value === false
              ? "border-navy bg-navy text-white"
              : "border-input text-muted-foreground hover:border-navy/60 hover:text-navy",
          )}
        >
          <X className="size-4" aria-hidden />
        </button>
      </div>
    </div>
  )
}

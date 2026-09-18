"use client"

import { Check, Minus, X } from "lucide-react"

import { cn } from "@/lib/utils"
import { NEUTRAL, NEUTRAL_MAX, type ChecklistAnswer } from "@/types/voyage"

/** The three marks in screen order. « – » sits between the two because it is
 *  neither; its selected tone is the muted grey, never a colour that reads as
 *  yes or no. Full class strings so Tailwind can see them. */
const MARKS: {
  value: ChecklistAnswer
  label: string
  Icon: typeof Check
  selected: string
  idle: string
}[] = [
  {
    value: true,
    label: "Oui",
    Icon: Check,
    selected: "border-success bg-success text-white",
    idle: "border-input text-muted-foreground hover:border-success/60 hover:text-success",
  },
  {
    value: NEUTRAL,
    label: "Neutre",
    Icon: Minus,
    selected: "border-muted-foreground bg-muted-foreground text-white",
    idle: "border-input text-muted-foreground hover:border-muted-foreground/60 hover:text-foreground",
  },
  {
    value: false,
    label: "Non",
    Icon: X,
    selected: "border-navy bg-navy text-white",
    idle: "border-input text-muted-foreground hover:border-navy/60 hover:text-navy",
  },
]

/**
 * One session-0 affirmation with its OUI / NEUTRE / NON marks.
 *
 * Buttons rather than one checkbox: the cahier prints boxes, and the
 * completion endpoint refuses a session that still has an unanswered item, so
 * "not answered yet" has to be a state the person can see.
 *
 * `neutralLocked` greys out « – » once the session already holds NEUTRAL_MAX
 * of them and this row is not one — the server refuses the next one anyway.
 */
export function ChecklistRow({
  n,
  text,
  value,
  disabled,
  neutralLocked,
  onChange,
}: {
  n: number
  text: string
  value: ChecklistAnswer | undefined
  disabled?: boolean
  neutralLocked?: boolean
  onChange: (next: ChecklistAnswer) => void
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
        {MARKS.map(({ value: mark, label, Icon, selected, idle }) => {
          const locked = mark === NEUTRAL && neutralLocked && value !== NEUTRAL
          return (
            <button
              key={label}
              type="button"
              disabled={disabled || locked}
              aria-pressed={value === mark}
              aria-label={`${label} — ${text}`}
              title={locked ? `${NEUTRAL_MAX} réponses neutres au maximum` : undefined}
              onClick={() => onChange(mark)}
              className={cn(
                "grid size-9 place-items-center rounded-lg border transition-colors disabled:cursor-not-allowed disabled:opacity-50",
                value === mark ? selected : idle,
              )}
            >
              <Icon className="size-4" aria-hidden />
            </button>
          )
        })}
      </div>
    </div>
  )
}

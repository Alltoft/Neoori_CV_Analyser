"use client"

import { cn } from "@/lib/utils"

/** Indexed by rank − 1. Past the third the ordinal is built, not listed. */
const RANK_LABELS = ["1er choix", "2e choix", "3e choix"]

/**
 * One lettered option of one scene. `label` and `text` are cahier and counselor-
 * manual wording served by the API — rendered as received, tutoiement included.
 * The scoring tag behind the option never leaves the server (spec decision 6).
 *
 * `rank` is the option's place in the person's ranking; the badge reads it out
 * in words, inside the button, so a screen reader hears the order too.
 */
export function OptionCard({
  letter,
  label,
  text,
  rank,
  disabled,
  onSelect,
}: {
  letter: string
  label: string
  text: string
  /** 1-based position in the ranking; undefined when not chosen. */
  rank?: number
  disabled?: boolean
  onSelect: () => void
}) {
  const selected = rank !== undefined

  return (
    <button
      type="button"
      disabled={disabled}
      aria-pressed={selected}
      onClick={onSelect}
      className={cn(
        "flex w-full gap-3 rounded-xl border p-3.5 text-left transition-colors",
        "disabled:cursor-not-allowed disabled:opacity-70",
        selected
          ? "border-navy bg-navy/5 ring-1 ring-navy"
          : "border-input bg-card hover:border-peach hover:bg-peach-soft/30",
      )}
    >
      <span
        className={cn(
          "grid size-7 shrink-0 place-items-center rounded-lg font-mono text-xs font-bold",
          selected ? "bg-navy text-peach" : "bg-secondary text-muted-foreground",
        )}
        aria-hidden
      >
        {letter}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block font-display text-sm font-semibold text-navy">{label}</span>
        <span className="mt-0.5 block text-sm leading-snug text-navy-700">{text}</span>
      </span>
      {selected && (
        <span className="shrink-0 self-start whitespace-nowrap rounded-full bg-navy px-2 py-0.5 font-mono text-[11px] font-semibold text-peach">
          {RANK_LABELS[rank - 1] ?? `${rank}e choix`}
        </span>
      )}
    </button>
  )
}

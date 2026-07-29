"use client"

import { Checkbox } from "@/components/ui/checkbox"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { cn } from "@/lib/utils"
import {
  CONDITION_FAMILIES,
  CONDITION_STATES,
  type ConditionEntry,
  type ConditionsValue,
} from "@/types/conditions"

/**
 * Bloc 5 — the eight condition families, each rated on three states, with
 * "C'est un point fort" as a separate axis.
 *
 * Everyone fills this, and it stays optional. The point of the extra checkbox
 * is that the three states can't express what matters: tolerating a demanding
 * requirement is a differentiator, and "me convient" never is. Merging them
 * into a four-way choice would lose that.
 */
export function ConditionsMatrix({
  value,
  onChange,
}: {
  value: ConditionsValue
  onChange: (next: ConditionsValue) => void
}) {
  const update = (family: string, patch: Partial<ConditionEntry>) => {
    const current = value[family] ?? { state: undefined, point_fort: false }
    onChange({ ...value, [family]: { ...current, ...patch } })
  }

  return (
    <div className="space-y-2">
      {/* Column headers — desktop only; each row repeats them on mobile. */}
      <div className="hidden items-center gap-3 px-3 pb-1 sm:grid sm:grid-cols-[1.1fr_repeat(3,minmax(0,1fr))_auto]">
        <span className="eyebrow text-muted-foreground">Famille</span>
        {CONDITION_STATES.map((s) => (
          <span key={s.value} className="eyebrow text-center text-muted-foreground">
            {s.short}
          </span>
        ))}
        <span className="eyebrow whitespace-nowrap text-muted-foreground">Point fort</span>
      </div>

      {CONDITION_FAMILIES.map((family) => {
        const entry = value[family.value]
        return (
          <fieldset
            key={family.value}
            className="rounded-xl bg-secondary/60 p-3 ring-1 ring-foreground/5 sm:grid sm:grid-cols-[1.1fr_repeat(3,minmax(0,1fr))_auto] sm:items-center sm:gap-3"
          >
            <legend className="sr-only">{family.label}</legend>

            <div className="mb-2 sm:mb-0">
              <p className="text-sm font-medium text-navy">{family.label}</p>
              <p className="text-[11px] leading-snug text-muted-foreground">{family.examples}</p>
            </div>

            <RadioGroup
              value={entry?.state ?? null}
              onValueChange={(next) => update(family.value, { state: next as ConditionEntry["state"] })}
              aria-label={family.label}
              className="mb-2 gap-1.5 sm:contents sm:mb-0"
            >
              {CONDITION_STATES.map((state) => (
                <label
                  key={state.value}
                  className={cn(
                    "flex cursor-pointer items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs transition-colors",
                    "hover:bg-background sm:justify-center",
                    entry?.state === state.value ? "bg-background font-medium text-navy" : "text-muted-foreground",
                  )}
                >
                  <RadioGroupItem value={state.value} />
                  <span className="sm:hidden">{state.label}</span>
                  <span className="hidden sm:inline sm:sr-only">{state.label}</span>
                </label>
              ))}
            </RadioGroup>

            <label className="flex cursor-pointer items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs text-muted-foreground hover:bg-background sm:justify-center">
              <Checkbox
                checked={entry?.point_fort ?? false}
                onCheckedChange={(checked) => update(family.value, { point_fort: checked })}
                aria-label={`${family.label} — c'est un point fort`}
              />
              <span className="sm:hidden">C&apos;est un point fort</span>
            </label>
          </fieldset>
        )
      })}
    </div>
  )
}

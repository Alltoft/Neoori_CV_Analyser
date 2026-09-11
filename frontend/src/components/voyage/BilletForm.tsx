"use client"

import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import type { BankBilletField } from "@/types/voyage"

/** Mirrors BILLET_MAX_CHARS in backend/app/routes/voyage.py — the server
 *  refuses a longer value with a 400, so the field stops accepting input at
 *  the same length instead of letting the person type past what will save. */
const BILLET_MAX_CHARS = 1000

/**
 * The billet de sortie. Every field is optional — session completion checks the
 * scored items only — and each label is the cahier's own line, trailing colon
 * included, served by GET /api/voyage/bank.
 */
export function BilletForm({
  fields,
  values,
  disabled,
  onChange,
}: {
  fields: BankBilletField[]
  values: Record<string, string>
  disabled?: boolean
  onChange: (key: string, next: string) => void
}) {
  if (fields.length === 0) return null

  return (
    <div className="space-y-4">
      {fields.map((f) => (
        <div key={f.key}>
          <Label htmlFor={`billet-${f.key}`} className="block text-sm leading-snug text-navy">
            {f.label}
          </Label>
          <Textarea
            id={`billet-${f.key}`}
            rows={3}
            maxLength={BILLET_MAX_CHARS}
            disabled={disabled}
            value={values[f.key] ?? ""}
            onChange={(e) => onChange(f.key, e.target.value)}
            className="mt-1.5 bg-card"
          />
        </div>
      ))}
    </div>
  )
}

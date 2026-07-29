"use client"

import { useState } from "react"
import { Check } from "lucide-react"

import { api } from "@/lib/api"
import { cn } from "@/lib/utils"

/**
 * Willingness-to-pay probe, shown once under a free report.
 *
 * PM: "à traiter comme un signal de hiérarchie, pas comme un prix de vente —
 * les gens déclarent toujours plus qu'ils ne paient." So the buckets are
 * coarse and ordered, and nothing in the app reads the answer back.
 *
 * It sits *below* the unlock CTA on purpose: asking what someone would pay
 * before offering them the thing reads as a negotiation.
 */
const BUCKETS = [
  { value: "moins_5", label: "Moins de 5 €" },
  { value: "5_10", label: "5 à 10 €" },
  { value: "10_20", label: "10 à 20 €" },
  { value: "plus_20", label: "Plus de 20 €" },
  { value: "je_ne_paierais_pas", label: "Je ne paierais pas" },
]

export function PriceProbe({ analysisId }: { analysisId: string }) {
  const [sent, setSent] = useState(false)
  const [busy, setBusy] = useState(false)

  const answer = async (bucket: string) => {
    if (busy) return
    setBusy(true)
    try {
      await api.post(`/analyses/${analysisId}/price-feedback`, {
        bucket,
        useful: bucket !== "je_ne_paierais_pas",
      })
    } catch {
      // A refused probe must never look like a broken report — thank them
      // either way and move on.
    }
    setSent(true)
  }

  if (sent) {
    return (
      <div className="no-print mt-4 flex items-center gap-2 rounded-xl bg-secondary px-4 py-3 text-xs text-muted-foreground">
        <Check className="size-3.5 shrink-0 text-success" aria-hidden />
        Merci — ça nous aide à ajuster.
      </div>
    )
  }

  return (
    <div className="no-print mt-4 rounded-xl bg-secondary px-4 py-3.5">
      <p className="text-xs font-medium text-navy">
        Ce diagnostic vous a-t-il été utile ? Selon vous, il vaudrait :
      </p>
      <div className="mt-2.5 flex flex-wrap gap-1.5">
        {BUCKETS.map((b) => (
          <button
            key={b.value}
            type="button"
            disabled={busy}
            onClick={() => answer(b.value)}
            className={cn(
              "rounded-full bg-background px-3 py-1.5 text-xs text-navy-700 ring-1 ring-foreground/10 transition-colors",
              "hover:bg-peach-soft hover:ring-orange/40",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              "disabled:opacity-50",
            )}
          >
            {b.label}
          </button>
        ))}
      </div>
    </div>
  )
}

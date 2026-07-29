"use client"

import { Sparkles } from "lucide-react"

import { summarize, type ConditionsValue } from "@/types/conditions"

function Row({ label, items, tone }: { label: string; items: string[]; tone: string }) {
  if (items.length === 0) return null
  return (
    <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
      <span className={`text-xs font-semibold ${tone}`}>{label}</span>
      <span className="text-xs text-navy-700">{items.join(" · ")}</span>
    </div>
  )
}

/**
 * « Ce que votre profil dit déjà » — builds as the person fills bloc 5.
 *
 * Pure client-side derivation, no request: the Parcours doc calls this the
 * moment someone sees their answers produce something, and a network
 * round-trip per keystroke would undercut that.
 *
 * The distinction it has to hold on to: « me convient » is a compatibility
 * criterion, not a strength. Only a point fort on a demanding requirement is
 * shown as one — the same rule the report applies.
 */
export function LiveSynthesis({ value }: { value: ConditionsValue }) {
  const s = summarize(value)
  const empty =
    s.points_forts.length === 0 &&
    s.me_convient.length === 0 &&
    s.possible_avec_adaptation.length === 0 &&
    s.a_eviter.length === 0

  return (
    <aside
      aria-live="polite"
      className="rounded-xl bg-peach-soft/60 p-4 ring-1 ring-orange/20"
    >
      <div className="mb-2 flex items-center gap-2">
        <Sparkles className="size-3.5 text-orange-dark" aria-hidden />
        <p className="font-display text-sm font-semibold text-navy">
          Ce que votre profil dit déjà
        </p>
      </div>

      {empty ? (
        <p className="text-xs text-muted-foreground">
          Renseignez vos conditions de travail ci-dessus : votre synthèse se construit ici,
          au fur et à mesure.
        </p>
      ) : (
        <div className="space-y-1.5">
          <Row label="Vos points forts" items={s.points_forts} tone="text-orange-dark" />
          <Row label="Ce qui vous convient" items={s.me_convient} tone="text-navy" />
          <Row label="Possible avec une adaptation" items={s.possible_avec_adaptation} tone="text-navy" />
          <Row label="À éviter" items={s.a_eviter} tone="text-navy" />

          {s.points_forts.length > 0 && (
            <p className="pt-1 text-[11px] leading-snug text-muted-foreground">
              Un point fort, c&apos;est une exigence que peu de gens tiennent — c&apos;est ce
              qui vous distingue vraiment dans le rapport.
            </p>
          )}
        </div>
      )}
    </aside>
  )
}

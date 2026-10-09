"use client"

import type { ReactNode } from "react"
import { Logo } from "@/components/brand/Logo"
import { Skeleton } from "@/components/ui/skeleton"
import { ReportSection } from "@/components/report/ReportSection"
import type { Analysis } from "@/types"

/** "Paid" is a property of what was generated, not of how it was paid for: a
 *  promo code, a Stripe payment and the advisor door produce the same report. */
export function isPaidReport(analysis: Analysis | null): boolean {
  const output = analysis?.output ?? {}
  return (
    analysis?.unlock_method != null ||
    (analysis?.sections_meta ?? []).some((m) => m.key in output && !m.tiers.includes("free"))
  )
}

/** The A4 report — header band, sections, page footer. One rendering for the
 *  owner's page, the no-login page and the counselor's page (four-doors spec). */
export function ReportDocument({
  analysis,
  loading,
  unlockHref,
  children,
}: {
  analysis: Analysis | null
  loading: boolean
  /** Where a locked section's « Débloquer → » points; null shows no link. */
  unlockHref: string | null
  /** Under the sections, above the page footer: an unlock offer, the price probe. */
  children?: ReactNode
}) {
  const output = analysis?.output ?? {}
  const hasOutput = Object.keys(output).length > 0
  // Order and titles come from the backend section registry. Never sort output
  // keys here.
  const meta = analysis?.sections_meta ?? []
  const generated = meta.filter((m) => m.key in output)
  // While loading, a short skeleton list (no phantom locked paid sections).
  const placeholder = meta.filter((m) => m.tiers.includes("free"))
  const isPaid = isPaidReport(analysis)
  const sections = hasOutput ? generated : placeholder
  const monthLabel = new Date(analysis?.created_at ?? "").toLocaleDateString("fr-FR", { month: "long", year: "numeric" })
  const name = [analysis?.inputs?.prenom, (analysis?.inputs?.nom ?? "").toUpperCase()].filter(Boolean).join(" ")

  return (
    <div className="report-shell">
      <div className="report-rule" />

      {/* Navy header band */}
      <div className="bg-navy px-8 pb-6 pt-6 text-white">
        <Logo tone="light" className="text-base" />
        {loading ? (
          <div className="mt-3 space-y-2">
            <Skeleton className="h-7 w-48 bg-white/20" />
            <Skeleton className="h-4 w-64 bg-white/10" />
          </div>
        ) : (
          <>
            <h1 className="mt-3 font-display text-2xl font-extrabold leading-tight text-white">{name || "—"}</h1>
            <p className="mt-1 text-sm italic text-peach">
              {`Cible : ${analysis?.inputs?.cible_visee?.slice(0, 60) ?? "—"} · ${monthLabel}`}
            </p>
          </>
        )}
      </div>

      <div className="px-8 py-7">
        {sections.map((m) => {
          const isPaidSection = !m.tiers.includes("free")
          const section = output[m.key]
          return (
            <ReportSection
              key={m.key}
              n={m.key}
              title={section?.title ?? m.title}
              section={section}
              render={m.render}
              paid={isPaidSection}
              locked={isPaidSection && !isPaid}
              unlockHref={unlockHref ?? undefined}
            />
          )
        })}

        {children}

        <div className="mt-8 flex items-center justify-between border-t border-border pt-4">
          <span className="font-mono text-[10px] text-muted-foreground">neoori · confidentiel</span>
          <span className="font-mono text-[10px] text-muted-foreground">{loading ? "" : monthLabel}</span>
        </div>
      </div>
    </div>
  )
}

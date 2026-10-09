"use client"

import { useEffect, useState } from "react"
import { useParams, useSearchParams } from "next/navigation"
import Link from "next/link"
import { AppBar } from "@/components/layout/AppBar"
import { Button } from "@/components/ui/button"
import { PriceProbe } from "@/components/report/PriceProbe"
import { ReportDocument, isPaidReport } from "@/components/report/ReportDocument"
import { api } from "@/lib/api"
import type { Analysis } from "@/types"
import { Printer } from "lucide-react"

export default function RapportPage() {
  const { id } = useParams<{ id: string }>()
  const searchParams = useSearchParams()
  const autoPrint = searchParams.get("print") === "1"
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!autoPrint || loading || !analysis) return
    const t = setTimeout(() => window.print(), 400)
    return () => clearTimeout(t)
  }, [autoPrint, loading, analysis])

  useEffect(() => {
    api.get<{ analysis: Analysis }>(`/analyses/${id}`)
      .then((r) => {
        setAnalysis(r.analysis)
        const a = r.analysis
        const prenom = a.inputs?.prenom ?? a.inputs?.nom ?? "Candidat"
        const cible = a.inputs?.cible_visee?.slice(0, 40) ?? ""
        const date = new Date(a.created_at ?? "").toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric" })
        document.title = `neoori — ${prenom}${cible ? ` — ${cible}` : ""} — ${date}`
      })
      .finally(() => setLoading(false))
    return () => { document.title = "neoori" }
  }, [id])

  const hasOutput = Object.keys(analysis?.output ?? {}).length > 0
  const isPaid = isPaidReport(analysis)

  return (
    <div className="min-h-screen bg-secondary">
      <AppBar />

      <div className="no-print sticky top-16 z-40 flex flex-wrap items-center justify-center gap-2 border-b border-border bg-secondary/95 py-3 backdrop-blur-sm">
        <Button variant="outline" size="sm" disabled={loading} onClick={() => setTimeout(() => window.print(), 50)}>
          <Printer className="size-3.5" /> PDF
        </Button>
      </div>

      <div className="px-4 py-8">
        <ReportDocument analysis={analysis} loading={loading} unlockHref={`/analyse/${id}/debloquer`}>
          {hasOutput && !isPaid && (
            <div className="no-print mt-2 flex flex-col items-start justify-between gap-4 rounded-xl bg-brand-gradient p-5 text-white sm:flex-row sm:items-center">
              <div>
                <p className="font-display font-bold">Débloquez les 6 sections restantes</p>
                <p className="mt-0.5 text-sm opacity-90">préconisations · réécriture · synthèse · pistes d’évolution · CV retravaillé</p>
              </div>
              <Button render={<Link href={`/analyse/${id}/debloquer`} />} size="lg" className="shrink-0 bg-white text-orange-dark hover:bg-white/90">
                Passer en payant — 9 €
              </Button>
            </div>
          )}
          {/* Below the unlock CTA on purpose: asking what someone would pay
              before offering them the thing reads as a negotiation. */}
          {hasOutput && !isPaid && <PriceProbe analysisId={id} />}
        </ReportDocument>
      </div>
    </div>
  )
}

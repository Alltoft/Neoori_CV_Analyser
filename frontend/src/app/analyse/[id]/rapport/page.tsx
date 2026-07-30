"use client"

import { useEffect, useState } from "react"
import { useParams, useSearchParams } from "next/navigation"
import Link from "next/link"
import { AppBar } from "@/components/layout/AppBar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ReportSection } from "@/components/report/ReportSection"
import { PriceProbe } from "@/components/report/PriceProbe"
import { api } from "@/lib/api"
import { copyToClipboard } from "@/lib/utils"
import type { Analysis } from "@/types"
import { Printer, Share2, Check } from "lucide-react"
import { Logo } from "@/components/brand/Logo"
import { normalizeParcours } from "@/types"

export default function RapportPage() {
  const { id } = useParams<{ id: string }>()
  const searchParams = useSearchParams()
  const autoPrint = searchParams.get("print") === "1"
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [loading, setLoading] = useState(true)
  const [view, setView] = useState<"rapport" | "conseiller">("rapport")
  const [shareState, setShareState] = useState<"idle" | "copied" | "failed">("idle")

  const share = async () => {
    const url = `${window.location.origin}/c/${analysis?.share_token}`
    const ok = await copyToClipboard(url)
    setShareState(ok ? "copied" : "failed")
    if (!ok) window.prompt("Copiez le lien conseiller :", url)
    setTimeout(() => setShareState("idle"), 2500)
  }

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

  const output = analysis?.output ?? {}
  const path = normalizeParcours(analysis?.inputs?._path)
  const hasOutput = Object.keys(output).length > 0

  // Order and titles come from the backend section registry. Never sort output
  // keys here: parcours 2 uses letter keys and parcours 3 Roman numerals, and
  // Number("A") - Number("B") is NaN, which silently leaves insertion order.
  const meta = analysis?.sections_meta ?? []
  const generated = meta.filter((m) => m.key in output)
  // While loading, show a short skeleton list (no phantom locked paid sections).
  const placeholder = meta.filter((m) => m.tiers.includes("free"))
  // "Paid" is a property of what was generated, not of how it was paid for:
  // a counselor code, a Stripe payment and a forced tier all produce the same
  // report. Deriving it from unlock_method alone rendered real content as
  // locked whenever the tier came from anywhere else.
  const isPaid =
    analysis?.unlock_method != null || generated.some((m) => !m.tiers.includes("free"))
  const counselorKeys = new Set(analysis?.counselor_keys ?? [])
  const sectionsToShow =
    view === "conseiller"
      ? generated.filter((m) => counselorKeys.has(m.key))
      : hasOutput
        ? generated
        : placeholder

  const monthLabel = new Date(analysis?.created_at ?? "").toLocaleDateString("fr-FR", { month: "long", year: "numeric" })

  return (
    <div className="min-h-screen bg-secondary">
      <AppBar />

      {/* Action bar */}
      <div className="no-print sticky top-16 z-40 flex flex-wrap items-center justify-center gap-2 border-b border-border bg-secondary/95 py-3 backdrop-blur-sm">
        <Tabs value={view} onValueChange={(v) => setView(v as typeof view)}>
          <TabsList className="border border-border bg-background">
            <TabsTrigger value="rapport" className="text-xs">Vue rapport</TabsTrigger>
            <TabsTrigger value="conseiller" className="text-xs">Vue conseiller</TabsTrigger>
          </TabsList>
        </Tabs>
        <div className="ml-2 flex gap-2">
          <Button variant="outline" size="sm" disabled={loading} onClick={() => setTimeout(() => window.print(), 50)}>
            <Printer className="size-3.5" /> PDF
          </Button>
          {analysis?.share_token && (
            <Button variant="outline" size="sm" onClick={share}>
              {shareState === "copied" ? <Check className="size-3.5 text-success" /> : <Share2 className="size-3.5" />}
              {shareState === "copied" ? "Lien copié" : "Partager au conseiller"}
            </Button>
          )}
        </div>
      </div>

      {/* A4 page */}
      <div className="px-4 py-8">
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
                <h1 className="mt-3 font-display text-2xl font-extrabold leading-tight text-white">
                  {[analysis?.inputs?.prenom, (analysis?.inputs?.nom ?? "").toUpperCase()].filter(Boolean).join(" ") || "—"}
                </h1>
                <p className="mt-1 text-sm italic text-peach">
                  {path === "3"
                    ? `Portrait de potentiel · ${monthLabel}`
                    : `Cible : ${analysis?.inputs?.cible_visee?.slice(0, 60) ?? "—"} · ${monthLabel}`}
                </p>
              </>
            )}
          </div>

          {/* Content */}
          <div className="px-8 py-7">
            {view === "conseiller" && <Badge variant="navy" className="mb-5">VERSION CONSEILLER</Badge>}

            {/* Key facts strip — counselor view */}
            {view === "conseiller" && analysis?.inputs && (
              <div className="mb-6 grid grid-cols-1 gap-3 rounded-lg bg-secondary p-4 text-xs sm:grid-cols-2 lg:grid-cols-4">
                {(path === "3"
                  ? [
                      ["Sous-profil", analysis.inputs._sub_profile?.toUpperCase() ?? "—"],
                      ["Aime", (analysis.inputs.aime ?? []).join(", ").slice(0, 60) || "—"],
                      ["Refus", (analysis.inputs.refuse ?? []).join(", ").slice(0, 60) || "—"],
                      ["Accompagnement", analysis.inputs.accompagnement ?? "—"],
                    ]
                  : [
                      ["Cible visée", analysis.inputs.cible_visee?.slice(0, 40)],
                      ["Mobilité", Array.isArray(analysis.inputs.type_mobilite) ? analysis.inputs.type_mobilite.join(" + ") : analysis.inputs.type_mobilite],
                      ["Posture actuelle", analysis.inputs.situation_actuelle],
                      ["Points sensibles", analysis.inputs.notes_specifiques || "—"],
                    ]
                ).map(([k, v]) => (
                  <div key={k}>
                    <p className="eyebrow text-muted-foreground">{k}</p>
                    <p className="mt-0.5 font-medium text-navy">{v}</p>
                  </div>
                ))}
              </div>
            )}

            {/* Sections */}
            {sectionsToShow.map((m) => {
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
                  counselor={view === "conseiller"}
                  locked={isPaidSection && !isPaid}
                  unlockHref={`/analyse/${id}/debloquer`}
                />
              )
            })}

            {/* Free-plan CTA — Chemin A only */}
            {view === "rapport" && path === "1" && hasOutput && !isPaid && (
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

            {/* Sits below the unlock CTA on purpose: asking what someone would
                pay before offering them the thing reads as a negotiation. */}
            {view === "rapport" && hasOutput && !isPaid && <PriceProbe analysisId={id} />}

            {/* Page footer */}
            <div className="mt-8 flex items-center justify-between border-t border-border pt-4">
              <span className="font-mono text-[10px] text-muted-foreground">neoori · confidentiel</span>
              <span className="font-mono text-[10px] text-muted-foreground">{loading ? "" : monthLabel}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

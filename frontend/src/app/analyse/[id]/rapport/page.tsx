"use client"

import React, { useEffect, useState } from "react"
import { useParams, useSearchParams } from "next/navigation"
import Link from "next/link"
import { AppBar } from "@/components/layout/AppBar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Separator } from "@/components/ui/separator"
import { api } from "@/lib/api"
import { cn, copyToClipboard } from "@/lib/utils"
import { SECTION_TITLES, FREE_SECTIONS, PAID_SECTIONS } from "@/types"
import type { Analysis } from "@/types"
import { Printer, Share2, Lock } from "lucide-react"
import ReactMarkdown, { type Components } from "react-markdown"

export default function RapportPage() {
  const { id } = useParams<{ id: string }>()
  const searchParams = useSearchParams()
  const autoPrint = searchParams.get("print") === "1"
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [loading,  setLoading]  = useState(true)
  const [view,     setView]     = useState<"rapport" | "conseiller">("rapport")
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
      .then(r => {
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
  const path = analysis?.inputs?._path ?? "A"
  const isPaid = "5" in output // unlocked when Sonnet generated all 9 sections (A only)

  const renderSection = (n: string) => {
    // Paywall logic only applies to Chemin A. Chemin B is free in all sections.
    const isPaidSection = path === "A" && (PAID_SECTIONS as readonly string[]).includes(n)
    const isLocked = isPaidSection && !isPaid
    const section = output[n]
    const title = section?.title ?? SECTION_TITLES[n] ?? `Section ${n}`

    return (
      <div key={n} className={cn("mb-6 print-break", isLocked && "opacity-60")}>
        <div className="flex items-center gap-2 mb-2">
          <span className="inline-flex items-center justify-center w-8 h-8 rounded-full border-2 border-foreground text-xs font-bold font-mono shrink-0">
            §{n}
          </span>
          <h2 className="font-bold text-base">{title}</h2>
          {isPaidSection && <Badge variant="outline" className="text-[10px] ml-auto">plan payant</Badge>}
        </div>

        {isLocked ? (
          <div className="flex items-center gap-2 py-4 text-muted-foreground">
            <Lock className="h-4 w-4" />
            <span className="text-sm">
              Disponible avec le plan complet.{" "}
              <Link href={`/analyse/${id}/debloquer`} className="text-primary underline">Débloquer →</Link>
            </span>
          </div>
        ) : section ? (
          <div className="text-sm leading-relaxed text-foreground/90 pl-10">
            {n === "3"
              ? <div className="flex flex-wrap gap-1.5 mt-1">
                  {(section.items?.length ? section.items.map((it: string | { fact?: string }) => typeof it === "string" ? it : (it.fact ?? String(it)))
                    : (section.body_markdown ?? "").split(/[·\n,]/).map((t: string) => t.trim()).filter(Boolean))
                    .map((tag: string, i: number) => <Badge key={i} variant="secondary" className="text-xs">{tag}</Badge>)}
                </div>
              : (() => {
                  const mdComponents = {
                    p:      ({ children }: {children: React.ReactNode}) => <p className="mb-2 last:mb-0">{children}</p>,
                    ul:     ({ children }: {children: React.ReactNode}) => <ul className="list-disc pl-4 mb-2 space-y-1">{children}</ul>,
                    ol:     ({ children }: {children: React.ReactNode}) => <ol className="list-decimal pl-4 mb-2 space-y-1">{children}</ol>,
                    li:     ({ children }: {children: React.ReactNode}) => <li>{children}</li>,
                    strong: ({ children }: {children: React.ReactNode}) => <strong className="font-semibold">{children}</strong>,
                    em:     ({ children }: {children: React.ReactNode}) => <em className="italic">{children}</em>,
                    h3:     ({ children }: {children: React.ReactNode}) => <h3 className="font-semibold mt-3 mb-1">{children}</h3>,
                    h4:     ({ children }: {children: React.ReactNode}) => <h4 className="font-medium mt-2 mb-1">{children}</h4>,
                  }
                  const content = section.body_markdown
                    || (section.items?.length
                        ? section.items.map((it: string | { fact?: string }) =>
                            `- ${typeof it === "string" ? it : (it.fact ?? String(it))}`
                          ).join("\n")
                        : "")
                  return <ReactMarkdown components={mdComponents as Components}>{content}</ReactMarkdown>
                })()
            }
          </div>
        ) : (
          <div className="pl-10 space-y-2">
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-4/5" />
            <Skeleton className="h-3 w-3/5" />
          </div>
        )}
        <Separator className="mt-6" />
      </div>
    )
  }

  const counselorSections = path === "B" ? ["1", "2", "8"] : ["1", "4", "5"]
  const allSections = Object.keys(output).length
    ? Object.keys(output).sort((a, b) => Number(a) - Number(b))
    : (path === "B" ? ["1", "2", "3", "8", "9"] : Object.keys(SECTION_TITLES))
  const sectionsToShow = view === "conseiller" ? counselorSections : allSections

  return (
    <div className="min-h-screen bg-secondary no-print-bg">
      <div className="no-print"><AppBar /></div>

      {/* Tabs bar */}
      <div className="no-print flex justify-center gap-2 py-4 bg-secondary sticky top-12 z-40 border-b border-border">
        <Tabs value={view} onValueChange={v => setView(v as typeof view)}>
          <TabsList className="bg-background border border-border">
            <TabsTrigger value="rapport" className="text-xs">vue rapport</TabsTrigger>
            <TabsTrigger value="conseiller" className="text-xs">vue conseiller</TabsTrigger>
          </TabsList>
        </Tabs>
        <div className="flex gap-2 ml-4">
          <Button variant="outline" size="sm" className="text-xs h-8" onClick={() => { setTimeout(() => window.print(), 50) }}>
            <Printer className="h-3.5 w-3.5 mr-1.5" />↓ PDF
          </Button>
          {analysis?.share_token && (
            <Button variant="outline" size="sm" className="text-xs h-8" onClick={share}>
              <Share2 className="h-3.5 w-3.5 mr-1.5" />
              {shareState === "copied" ? "✓ lien conseiller copié" : "↗ partager au conseiller"}
            </Button>
          )}
        </div>
      </div>

      {/* A4 page */}
      <div className="py-6">
        <div className="report-shell">
          {/* Page header */}
          {view === "conseiller" && (
            <Badge className="bg-primary text-primary-foreground mb-4">VERSION CONSEILLER</Badge>
          )}

          {loading ? (
            <div className="space-y-3">
              <Skeleton className="h-6 w-48" />
              <Skeleton className="h-4 w-64" />
            </div>
          ) : (
            <div className="flex justify-between items-end border-b-2 border-foreground pb-3 mb-6">
              <div>
                <p className="text-[10px] font-mono tracking-widest uppercase text-muted-foreground">
                  NEOORI · ANALYSE DE CV
                </p>
                <h2 className="text-xl font-bold mt-1">
                  {[analysis?.inputs?.prenom, (analysis?.inputs?.nom ?? "").toUpperCase()]
                    .filter(Boolean).join(" ") || "—"}
                </h2>
                <p className="text-xs text-muted-foreground">
                  {path === "B"
                    ? `Portrait de potentiel · ${new Date(analysis?.created_at ?? "").toLocaleDateString("fr-FR", { month: "long", year: "numeric" })}`
                    : `Cible : ${analysis?.inputs?.cible_visee?.slice(0, 60) ?? "—"} · ${new Date(analysis?.created_at ?? "").toLocaleDateString("fr-FR", { month: "long", year: "numeric" })}`}
                </p>
              </div>
              <span className="font-bold text-lg tracking-tight">neoori</span>
            </div>
          )}

          {/* Key facts strip for counselor view */}
          {view === "conseiller" && analysis?.inputs && (
            <div className="grid grid-cols-4 gap-3 rounded-lg bg-secondary p-4 mb-6 text-xs">
              {(path === "B"
                ? [
                    ["Sous-profil",     analysis.inputs._sub_profile?.toUpperCase() ?? "—"],
                    ["Aime",            (analysis.inputs.aime ?? []).join(", ").slice(0, 60) || "—"],
                    ["Refus",           (analysis.inputs.refuse ?? []).join(", ").slice(0, 60) || "—"],
                    ["Accompagnement",  analysis.inputs.accompagnement ?? "—"],
                  ]
                : [
                    ["Cible visée",       analysis.inputs.cible_visee?.slice(0, 40)],
                    ["Mobilité",          Array.isArray(analysis.inputs.type_mobilite) ? analysis.inputs.type_mobilite.join(" + ") : analysis.inputs.type_mobilite],
                    ["Posture actuelle",  analysis.inputs.situation_actuelle],
                    ["Points sensibles",  analysis.inputs.notes_specifiques || "—"],
                  ]
              ).map(([k, v]) => (
                <div key={k}>
                  <p className="font-mono text-[10px] uppercase text-muted-foreground">{k}</p>
                  <p className="font-medium mt-0.5">{v}</p>
                </div>
              ))}
            </div>
          )}

          {/* Sections */}
          {sectionsToShow.map(renderSection)}

          {/* Free plan CTA — Chemin A only */}
          {view === "rapport" && path === "A" && !isPaid && (
            <div className="rounded-lg bg-primary text-primary-foreground p-5 flex items-center justify-between mt-2 no-print">
              <div>
                <p className="font-semibold">Débloquez les 5 sections restantes</p>
                <p className="text-sm opacity-85 mt-0.5">préconisations · réécriture · synthèse · pistes d'évolution · CV retravaillé</p>
              </div>
              <Button render={<Link href={`/analyse/${id}/debloquer`}/>} variant="secondary" size="sm" className="shrink-0">passer en payant — 9 € →</Button>
            </div>
          )}

          {/* Page footer */}
          <div className="flex justify-between mt-8 pt-4 border-t border-border">
            <span className="text-[10px] font-mono text-muted-foreground">neoori · v1.3 · confidentiel</span>
            <span className="text-[10px] font-mono text-muted-foreground">1 / 1</span>
          </div>
        </div>
      </div>
    </div>
  )
}

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
import { Logo } from "@/components/brand/Logo"

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
      <div key={n} className={cn("mb-7 print-break", isLocked && "opacity-60")}>
        <div className="flex items-stretch mb-3 rounded-md overflow-hidden">
          <span className="flex items-center justify-center w-9 shrink-0 bg-orange text-white text-[11px] font-bold font-mono">
            §{n}
          </span>
          <div className="flex items-center gap-2 flex-1 bg-navy px-3 py-2">
            <h2 className="font-display font-bold text-sm uppercase tracking-wide text-white leading-tight">{title}</h2>
            {isPaidSection && <Badge variant="peach" className="text-[10px] ml-auto shrink-0">plan payant</Badge>}
          </div>
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
          <div className="text-sm leading-relaxed text-foreground/90">
            {n === "3"
              ? <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5 mt-1">
                  {(section.items?.length ? section.items.map((it: string | { fact?: string }) => typeof it === "string" ? it : (it.fact ?? String(it)))
                    : (section.body_markdown ?? "").split(/[·\n,]/).map((t: string) => t.trim()).filter(Boolean))
                    .map((tag: string, i: number) => <span key={i} className="rounded-md bg-secondary text-navy text-xs font-medium px-2.5 py-1.5 text-center">{tag}</span>)}
                </div>
              : (() => {
                  const mdComponents = {
                    p:      ({ children }: {children: React.ReactNode}) => <p className="mb-2 last:mb-0">{children}</p>,
                    ul:     ({ children }: {children: React.ReactNode}) => <ul className="list-disc pl-4 mb-2 space-y-1 marker:text-orange">{children}</ul>,
                    ol:     ({ children }: {children: React.ReactNode}) => <ol className="list-decimal pl-4 mb-2 space-y-1 marker:text-orange">{children}</ol>,
                    li:     ({ children }: {children: React.ReactNode}) => <li>{children}</li>,
                    strong: ({ children }: {children: React.ReactNode}) => <strong className="font-semibold text-navy">{children}</strong>,
                    em:     ({ children }: {children: React.ReactNode}) => <em className="italic">{children}</em>,
                    a:      ({ href, children }: {href?: string, children: React.ReactNode}) => <a href={href} className="text-orange underline underline-offset-2">{children}</a>,
                    blockquote: ({ children }: {children: React.ReactNode}) => <blockquote className="my-3 rounded-md border-l-[3px] border-orange bg-peach-soft/60 px-3.5 py-2.5 text-navy [&_p]:mb-0">{children}</blockquote>,
                    h3:     ({ children }: {children: React.ReactNode}) => <h3 className="font-display font-bold text-navy mt-4 mb-1.5">{children}</h3>,
                    h4:     ({ children }: {children: React.ReactNode}) => <h4 className="font-display font-semibold text-navy mt-3 mb-1">{children}</h4>,
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
          <div className="space-y-2">
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
      <div className="no-print flex justify-center gap-2 py-4 bg-secondary sticky top-14 z-40 border-b border-border">
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
          {/* Orange top rule */}
          <div className="report-rule" />

          {/* Navy header band */}
          <div className="bg-navy text-white px-8 pt-5 pb-6">
            <Logo tone="light" className="text-base" />
            {loading ? (
              <div className="space-y-2 mt-3">
                <Skeleton className="h-7 w-48 bg-white/20" />
                <Skeleton className="h-4 w-64 bg-white/10" />
              </div>
            ) : (
              <>
                <h1 className="font-display font-extrabold text-2xl text-white mt-3 leading-tight">
                  {[analysis?.inputs?.prenom, (analysis?.inputs?.nom ?? "").toUpperCase()]
                    .filter(Boolean).join(" ") || "—"}
                </h1>
                <p className="text-sm text-peach italic mt-1">
                  {path === "B"
                    ? `Portrait de potentiel · ${new Date(analysis?.created_at ?? "").toLocaleDateString("fr-FR", { month: "long", year: "numeric" })}`
                    : `Cible : ${analysis?.inputs?.cible_visee?.slice(0, 60) ?? "—"} · ${new Date(analysis?.created_at ?? "").toLocaleDateString("fr-FR", { month: "long", year: "numeric" })}`}
                </p>
              </>
            )}
          </div>

          {/* Content */}
          <div className="px-8 py-7">
          {view === "conseiller" && (
            <Badge variant="navy" className="mb-5">VERSION CONSEILLER</Badge>
          )}

          {/* Key facts strip for counselor view */}
          {view === "conseiller" && analysis?.inputs && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 rounded-lg bg-secondary p-4 mb-6 text-xs">
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
                  <p className="font-mono text-[10px] tracking-wide uppercase text-orange">{k}</p>
                  <p className="font-medium mt-0.5 text-navy">{v}</p>
                </div>
              ))}
            </div>
          )}

          {/* Sections */}
          {sectionsToShow.map(renderSection)}

          {/* Free plan CTA — Chemin A only */}
          {view === "rapport" && path === "A" && !isPaid && (
            <div className="rounded-xl bg-brand-gradient text-white p-5 flex items-center justify-between gap-4 mt-2 no-print">
              <div>
                <p className="font-display font-bold">Débloquez les 5 sections restantes</p>
                <p className="text-sm opacity-90 mt-0.5">préconisations · réécriture · synthèse · pistes d'évolution · CV retravaillé</p>
              </div>
              <Button render={<Link href={`/analyse/${id}/debloquer`}/>} size="sm" className="shrink-0 bg-white text-orange hover:bg-white/90">passer en payant — 9 € →</Button>
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
    </div>
  )
}

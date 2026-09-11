"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { AppBar } from "@/components/layout/AppBar"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { StatusBadge } from "@/components/ui/status-badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Separator } from "@/components/ui/separator"
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { api, ApiError } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { copyToClipboard } from "@/lib/utils"
import { fmtDate } from "@/lib/format"
import { getVoyage } from "@/lib/voyage"
import type { Analysis } from "@/types"
import type { Voyage } from "@/types/voyage"
import { PlusCircle, ExternalLink, Download, MoreHorizontal, Trash2, Check, Link2, ArrowRight } from "lucide-react"
import { normalizeParcours } from "@/types"

function cardTitle(a: Analysis) {
  if (a.status === "draft") return "Brouillon"
  return a.inputs?.cible_visee?.slice(0, 60) || (normalizeParcours(a.inputs?._path) === "3" ? "Portrait de potentiel" : "Analyse")
}

export default function EspacePage() {
  const { user } = useAuth()
  const [analyses, setAnalyses] = useState<Analysis[]>([])
  const [loading, setLoading] = useState(true)
  const [copiedToken, setCopiedToken] = useState<string | null>(null)
  const [origin, setOrigin] = useState("")
  const [voyage, setVoyage] = useState<Voyage | null>(null)
  const [voyageLoaded, setVoyageLoaded] = useState(false)

  useEffect(() => setOrigin(window.location.origin), [])

  const copyShare = async (token: string) => {
    const url = `${window.location.origin}/c/${token}`
    const ok = await copyToClipboard(url)
    if (!ok) {
      window.prompt("Copiez le lien conseiller :", url)
      return
    }
    setCopiedToken(token)
    setTimeout(() => setCopiedToken((t) => (t === token ? null : t)), 2500)
  }

  useEffect(() => {
    api.get<{ analyses: Analysis[] }>("/analyses/")
      .then((r) => setAnalyses(r.analyses))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  // The voyage is never required (spec decision 11) — this strip is an offer,
  // so a failed read renders nothing rather than an error (D-S9): voyageLoaded
  // only ever flips to true on success, so the strip stays absent for good on
  // a failed read instead of flashing an empty state.
  useEffect(() => {
    getVoyage()
      .then((v) => { setVoyage(v); setVoyageLoaded(true) })
      .catch(() => {})
  }, [])

  const remove = async (id: string) => {
    if (!window.confirm("Supprimer cette analyse ? Cette action est définitive.")) return
    try {
      await api.delete(`/analyses/${id}`)
      setAnalyses((prev) => prev.filter((a) => a.id !== id))
    } catch (e) {
      alert(e instanceof ApiError ? e.message : "Erreur lors de la suppression.")
    }
  }

  const shareable = analyses.find((a) => a.status === "success" && a.share_token)

  return (
    <div className="min-h-screen bg-background">
      <AppBar />
      <div className="mx-auto max-w-6xl px-5 py-10 sm:px-8">
        <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="font-display text-2xl font-bold text-navy">Mon espace</h1>
            <p className="mt-1 text-sm text-muted-foreground">Vos analyses et vos brouillons.</p>
          </div>
          <Button render={<Link href="/analyse" />} size="lg">
            <PlusCircle /> Nouvelle analyse
          </Button>
        </div>

        {/* Le voyage — the fourth scenario, on the charter's inverted surface so
            it does not read as a fourth parcours card. */}
        {voyageLoaded && voyage && (
          <div className="mb-6 overflow-hidden rounded-2xl bg-navy shadow-card">
            <div className="voyage-rule" />
            <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center">
              <div className="min-w-0 flex-1">
                <p className="eyebrow text-peach">Le voyage</p>
                <p className="mt-1 font-display text-base font-bold text-white">
                  {voyage.sessions_completed.length} session
                  {voyage.sessions_completed.length > 1 ? "s" : ""} sur 6
                </p>
                {voyage.micro_phrase ? (
                  <p className="mt-1.5 line-clamp-2 text-sm italic text-white/80">
                    « {voyage.micro_phrase} »
                  </p>
                ) : null}
              </div>
              {/* R25: the label and target depend on the portrait's state, not
                  just "has a voyage" — a validated portrait leads straight to
                  it, an unvalidated one with a share_token surfaces the
                  counselor link, otherwise it is just "continue the voyage". */}
              <Button
                render={
                  <Link
                    href={voyage.portrait_status === "validated" ? "/voyage/portrait" : "/voyage"}
                  />
                }
                size="lg"
                className="shrink-0 bg-white text-navy hover:bg-white/90"
              >
                {voyage.portrait_status === "validated"
                  ? "Voir mon portrait"
                  : voyage.share_token
                    ? "Lien pour mon conseiller"
                    : "Continuer"}
                <ArrowRight />
              </Button>
            </div>
          </div>
        )}

        {voyageLoaded && !voyage && (
          <Link
            href="/voyage"
            className="group mb-6 block overflow-hidden rounded-2xl bg-navy shadow-card transition-shadow hover:shadow-float"
          >
            <span className="voyage-rule block" />
            <div className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center">
              <div className="min-w-0 flex-1">
                <p className="eyebrow text-peach">Le voyage</p>
                <p className="mt-1 font-display text-base font-bold text-white">
                  Six sessions pour poser ce que vous savez déjà de vous.
                </p>
                <p className="mt-1 text-sm text-white/80">
                  La première prend 5 minutes et se fait en autonomie.
                </p>
              </div>
              <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-white/10 px-3 py-1.5 text-xs font-medium text-white">
                Commencer
                <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-0.5" aria-hidden />
              </span>
            </div>
          </Link>
        )}

        {loading ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[1, 2, 3].map((i) => <Skeleton key={i} className="h-52 rounded-2xl" />)}
          </div>
        ) : analyses.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed border-border bg-secondary py-20 text-center">
            <span className="grid size-12 place-items-center rounded-full bg-peach-soft text-orange-dark"><PlusCircle className="size-6" /></span>
            <p className="font-display font-semibold text-navy">Votre première analyse</p>
            <p className="text-sm text-muted-foreground">~2 min · 8 champs</p>
            <Button render={<Link href="/analyse" />} size="lg" className="mt-2">
              Commencer <ArrowRight />
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {analyses.map((a) => (
              <div key={a.id} className="flex flex-col gap-3 rounded-2xl bg-card p-4 ring-1 ring-foreground/10 shadow-soft hover-lift">
                <div className="flex items-start justify-between gap-2">
                  <Badge variant="outline" className="shrink-0 font-mono text-[10px]">{fmtDate(a.created_at)}</Badge>
                  <DropdownMenu>
                    <DropdownMenuTrigger render={<Button variant="ghost" size="icon-sm" aria-label="Options" />}>
                      <MoreHorizontal className="size-4" />
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem variant="destructive" onClick={() => remove(a.id)}>
                        <Trash2 /> Supprimer
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>

                <h3 className="line-clamp-2 font-display text-sm font-semibold leading-tight text-navy">{cardTitle(a)}</h3>

                <div className="flex flex-wrap gap-1.5">
                  <StatusBadge status={a.status} />
                  {a.output && Object.keys(a.output).length > 0 && (
                    <Badge variant="outline" className="text-[10px]">{Object.keys(a.output).length} sections</Badge>
                  )}
                </div>

                <div className="min-h-[48px] space-y-1 rounded-md bg-secondary p-2">
                  {a.output?.["1"]?.body_markdown ? (
                    <p className="line-clamp-3 text-[11px] text-muted-foreground">{a.output["1"].body_markdown}</p>
                  ) : (
                    <div className="space-y-1.5">
                      {[100, 80, 55].map((w, i) => <div key={i} className="h-1.5 rounded-full bg-border" style={{ width: `${w}%` }} />)}
                    </div>
                  )}
                </div>

                <div className="mt-auto flex gap-1.5 pt-1">
                  {a.status === "draft" ? (
                    <Button render={<Link href={`/analyse/nouveau?draft=${a.id}`} />} size="sm" variant="outline" className="flex-1">
                      <ExternalLink className="size-3.5" /> Reprendre
                    </Button>
                  ) : (
                    <>
                      <Button render={<Link href={`/analyse/${a.id}/rapport`} />} size="sm" variant="outline" className="flex-1">
                        <ExternalLink className="size-3.5" /> Ouvrir
                      </Button>
                      <Button render={<Link href={`/analyse/${a.id}/rapport?print=1`} />} size="icon-sm" variant="outline" aria-label="Télécharger le PDF">
                        <Download className="size-3.5" />
                      </Button>
                      {a.share_token && (
                        <Button size="icon-sm" variant="outline" aria-label="Copier le lien conseiller" onClick={() => copyShare(a.share_token!)}>
                          {copiedToken === a.share_token ? <Check className="size-3.5 text-success" /> : <Link2 className="size-3.5" />}
                        </Button>
                      )}
                    </>
                  )}
                </div>
              </div>
            ))}

            {/* New analysis card */}
            <Link
              href="/analyse"
              className="flex min-h-[200px] flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-border bg-secondary transition-colors hover:border-orange/50"
            >
              <span className="grid size-10 place-items-center rounded-full bg-peach-soft text-orange-dark"><PlusCircle className="size-5" /></span>
              <span className="text-sm font-medium text-navy">Nouvelle analyse</span>
              <span className="text-xs text-muted-foreground">~2 min</span>
            </Link>
          </div>
        )}

        <Separator className="my-8" />

        {/* Bottom strip */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[2fr_1fr]">
          <div className="flex flex-col gap-3 rounded-2xl bg-card p-4 ring-1 ring-foreground/10 sm:flex-row sm:items-center">
            <span className="shrink-0 text-sm font-medium text-navy">Partagez avec votre conseiller</span>
            {shareable ? (
              <>
                <code className="flex-1 truncate rounded-md bg-secondary px-2 py-1.5 font-mono text-xs text-muted-foreground">
                  {origin}/c/{shareable.share_token}
                </code>
                <Button size="sm" variant="outline" className="shrink-0" onClick={() => copyShare(shareable.share_token!)}>
                  {copiedToken === shareable.share_token ? <><Check className="size-3.5 text-success" /> Copié</> : "Copier"}
                </Button>
              </>
            ) : (
              <span className="text-xs text-muted-foreground">Aucune analyse complète disponible pour le moment.</span>
            )}
          </div>

          <div className="flex items-center justify-between gap-3 rounded-2xl bg-card p-4 ring-1 ring-foreground/10">
            <div>
              <p className="eyebrow text-muted-foreground">Crédits restants</p>
              <p className="mt-1 font-display text-xl font-bold text-navy">
                {user?.credits_remaining ?? "—"} analyse{(user?.credits_remaining ?? 0) > 1 ? "s" : ""}
              </p>
            </div>
            <Button render={<Link href="/analyse" />} size="sm">
              <PlusCircle /> Lancer
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

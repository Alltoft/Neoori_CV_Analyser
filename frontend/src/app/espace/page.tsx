"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { AppBar } from "@/components/layout/AppBar"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Separator } from "@/components/ui/separator"
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { api, ApiError } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import type { Analysis } from "@/types"
import { PlusCircle, ExternalLink, Download, MoreHorizontal, Trash2 } from "lucide-react"

function statusLabel(s: string) {
  if (s === "success") return "complète"
  if (s === "draft")   return "brouillon"
  return s
}

export default function EspacePage() {
  const { user } = useAuth()
  const [analyses, setAnalyses] = useState<Analysis[]>([])
  const [loading,  setLoading]  = useState(true)

  useEffect(() => {
    api.get<{ analyses: Analysis[] }>("/analyses/")
      .then(r => setAnalyses(r.analyses))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const remove = async (id: string) => {
    try {
      await api.delete(`/analyses/${id}`)
      setAnalyses(prev => prev.filter(a => a.id !== id))
    } catch (e) {
      alert(e instanceof ApiError ? e.message : "Erreur.")
    }
  }

  return (
    <div className="min-h-screen bg-background">
      <AppBar />
      <div className="max-w-[1100px] mx-auto px-8 py-8">
        <div className="flex items-end justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold">Mon espace</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Vos analyses, vos brouillons{user?.role === "counselor" ? ", votre portefeuille candidats" : ""}.
            </p>
          </div>
          <Button render={<Link href="/analyse/nouveau"/>} className="bg-primary hover:bg-primary/90 text-primary-foreground">
            <PlusCircle className="h-4 w-4 mr-1.5" />+ nouvelle analyse
          </Button>
        </div>

        {loading ? (
          <div className="grid grid-cols-3 gap-4">
            {[1,2,3].map(i => <Skeleton key={i} className="h-48 rounded-lg" />)}
          </div>
        ) : analyses.length === 0 ? (
          <div className="rounded-lg border-2 border-dashed border-border bg-secondary flex flex-col items-center justify-center py-20 gap-3">
            <span className="text-3xl text-muted-foreground/40">+</span>
            <p className="font-medium">Votre première analyse</p>
            <p className="text-sm text-muted-foreground">~2 min · 8 champs</p>
            <Button render={<Link href="/analyse/nouveau"/>} className="mt-2 bg-primary hover:bg-primary/90 text-primary-foreground">Commencer →</Button>
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-4">
            {analyses.map(a => (
              <div key={a.id} className="rounded-lg border border-border bg-card p-4 flex flex-col gap-3">
                <div className="flex items-start justify-between gap-2">
                  <Badge variant="outline" className="text-[10px] font-mono shrink-0">
                    {new Date(a.created_at).toLocaleDateString("fr-FR", { day: "numeric", month: "short" })}
                  </Badge>
                  <DropdownMenu>
                    <DropdownMenuTrigger render={<Button variant="ghost" size="sm" className="h-6 w-6 p-0"/>}>
                      <MoreHorizontal className="h-3.5 w-3.5" />
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem className="text-destructive" onClick={() => remove(a.id)}>
                        <Trash2 className="h-3.5 w-3.5 mr-2" />Supprimer
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>

                <h3 className="font-semibold text-sm leading-tight line-clamp-2">
                  {a.inputs?.cible_visee?.slice(0, 60) ?? "Brouillon"}
                </h3>

                <div className="flex flex-wrap gap-1.5">
                  <Badge variant="secondary" className="text-[10px]">{statusLabel(a.status)}</Badge>
                  {a.output && (
                    <Badge variant="outline" className="text-[10px]">
                      {Object.keys(a.output).length} sections
                    </Badge>
                  )}
                </div>

                {/* Mini preview */}
                <div className="rounded bg-secondary p-2 space-y-1 min-h-[48px]">
                  {a.output?.["1"]?.body_markdown
                    ? <p className="text-[11px] text-muted-foreground line-clamp-3">{a.output["1"].body_markdown}</p>
                    : <div className="space-y-1.5">{[1,2,3].map(i => <div key={i} className="h-1.5 bg-border rounded-full" style={{ width: `${[100,80,55][i-1]}%` }} />)}</div>
                  }
                </div>

                <div className="flex gap-1.5 mt-auto pt-1">
                  {a.status === "draft" ? (
                    <Button render={<Link href={`/analyse/nouveau?draft=${a.id}`}/>} size="sm" variant="outline" className="text-xs h-7 flex-1">
                      <ExternalLink className="h-3 w-3 mr-1" />reprendre
                    </Button>
                  ) : (
                    <>
                      <Button render={<Link href={`/analyse/${a.id}/rapport`}/>} size="sm" variant="outline" className="text-xs h-7 flex-1">
                        <ExternalLink className="h-3 w-3 mr-1" />ouvrir
                      </Button>
                      <Button render={<Link href={`/analyse/${a.id}/rapport?print=1`}/>} size="sm" variant="outline" className="text-xs h-7 w-7 p-0">
                        <Download className="h-3 w-3" />
                      </Button>
                      {a.share_token && (
                        <Button size="sm" variant="outline" className="text-xs h-7 w-7 p-0"
                          onClick={() => navigator.clipboard.writeText(`${window.location.origin}/c/${a.share_token}`)}>
                          <ExternalLink className="h-3 w-3" />
                        </Button>
                      )}
                    </>
                  )}
                </div>
              </div>
            ))}

            {/* New analysis card */}
            <Link href="/analyse/nouveau"
              className="rounded-lg border-2 border-dashed border-border bg-secondary flex flex-col items-center justify-center gap-2 min-h-[200px] hover:border-primary/50 transition-colors">
              <span className="text-2xl text-muted-foreground">+</span>
              <span className="text-sm font-medium">nouvelle analyse</span>
              <span className="text-xs text-muted-foreground">~2 min</span>
            </Link>
          </div>
        )}

        <Separator className="my-8" />

        {/* Bottom strip */}
        <div className="grid grid-cols-[2fr_1fr] gap-4">
          <div className="rounded-lg border border-border bg-card p-4 flex items-center gap-4">
            <span className="font-medium text-sm shrink-0">Partagez avec votre conseiller</span>
            {analyses[0]?.share_token ? (
              <>
                <code className="flex-1 text-xs bg-secondary px-2 py-1 rounded font-mono text-muted-foreground truncate">
                  {typeof window !== "undefined" ? window.location.origin : "neoori.fr"}/c/{analyses[0].share_token}
                </code>
                <Button size="sm" variant="outline" className="text-xs shrink-0"
                  onClick={() => navigator.clipboard.writeText(`${window.location.origin}/c/${analyses[0].share_token}`)}>
                  copier
                </Button>
              </>
            ) : (
              <span className="text-xs text-muted-foreground">Aucune analyse complète disponible.</span>
            )}
          </div>
          <div className="rounded-lg border border-border bg-card p-4 flex items-center justify-between">
            <div>
              <p className="text-[10px] font-mono uppercase text-muted-foreground">Crédits restants</p>
              <p className="text-xl font-bold mt-0.5">{user?.credits_remaining ?? "—"} analyse{(user?.credits_remaining ?? 0) > 1 ? "s" : ""}</p>
            </div>
            <Button size="sm" className="bg-primary hover:bg-primary/90 text-primary-foreground text-xs">
              recharger
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

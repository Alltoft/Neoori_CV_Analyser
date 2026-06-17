"use client"

import { useCallback, useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { StatusBadge } from "@/components/ui/status-badge"
import { api } from "@/lib/api"
import { fmtDateTime, fmtInt } from "@/lib/format"
import type { PromptVersion } from "@/types"

interface LogEntry {
  id: string; created_at: string
  inputs: { prenom?: string; cible_visee?: string } | null
  status: string; prompt_version_id: string | null
  tokens_in: number | null; tokens_out: number | null
}
interface ListResponse {
  analyses: LogEntry[]; total: number; pages: number; page: number
}

/* Status filter options — values stay the backend tokens, labels are localized. */
const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: "tous", label: "Tous" },
  { value: "success", label: "Succès" },
  { value: "running", label: "En cours" },
  { value: "queued", label: "En file" },
  { value: "error", label: "Échec" },
  { value: "timeout", label: "Expiré" },
]

export default function AnalysesPage() {
  const [data, setData] = useState<ListResponse | null>(null)
  const [versions, setVersions] = useState<PromptVersion[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [page, setPage] = useState(1)
  const [status, setStatus] = useState("")
  const [appliedStatus, setAppliedStatus] = useState("")
  const [searchInput, setSearchInput] = useState("")
  const [appliedSearch, setAppliedSearch] = useState("")
  const [from, setFrom] = useState("")
  const [to, setTo] = useState("")
  const [appliedFrom, setAppliedFrom] = useState("")
  const [appliedTo, setAppliedTo] = useState("")

  const load = useCallback(async (p: number, s: string, q: string, f: string, t: string) => {
    setLoading(true)
    const params = new URLSearchParams({ page: String(p) })
    if (s) params.set("status", s)
    if (q) params.set("search", q)
    if (f) params.set("from", f)
    if (t) params.set("to", t)
    try {
      const res = await api.get<ListResponse>(`/admin/analyses?${params}`)
      setData(res)
      setError(null)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erreur de chargement")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    api.get<{ prompts: PromptVersion[] }>("/prompts/")
      .then(r => setVersions(r.prompts))
      .catch(() => {})
    load(1, "", "", "", "")
  }, [load])

  const apply = () => {
    setPage(1)
    setAppliedStatus(status)
    setAppliedSearch(searchInput)
    setAppliedFrom(from)
    setAppliedTo(to)
    load(1, status, searchInput, from, to)
  }

  const reset = () => {
    setPage(1)
    setStatus(""); setAppliedStatus("")
    setSearchInput(""); setAppliedSearch("")
    setFrom(""); setTo("")
    setAppliedFrom(""); setAppliedTo("")
    load(1, "", "", "", "")
  }

  const goPage = (p: number) => {
    setPage(p)
    load(p, appliedStatus, appliedSearch, appliedFrom, appliedTo)
  }

  const versionLabel = (id: string | null): string =>
    versions.find(v => v.id === id)?.version_label ?? "—"

  return (
    <>
      <div className="mb-5">
        <p className="eyebrow text-orange-dark">Administration</p>
        <h1 className="font-display font-bold text-2xl text-navy mt-1">Analyses</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Historique de toutes les analyses, avec filtres par statut, date et texte.
        </p>
      </div>

      <div className="rounded-2xl border border-border bg-card shadow-soft p-4 sm:p-5">
        {/* Filter bar — stacks on mobile, inline from sm */}
        <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end mb-4">
          <div className="flex flex-col gap-1.5 sm:w-44">
            <span className="eyebrow text-muted-foreground">Statut</span>
            <Select
              value={status || "tous"}
              onValueChange={v => v !== null && setStatus(v === "tous" ? "" : v)}
            >
              <SelectTrigger className="h-10 w-full">
                <SelectValue placeholder="Tous les statuts" />
              </SelectTrigger>
              <SelectContent>
                {STATUS_OPTIONS.map(opt => (
                  <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex flex-col gap-1.5 sm:w-40">
            <span className="eyebrow text-muted-foreground">Du</span>
            <Input
              type="date"
              aria-label="Date de début"
              value={from}
              onChange={e => setFrom(e.target.value)}
              className="h-10 w-full"
            />
          </div>

          <div className="flex flex-col gap-1.5 sm:w-40">
            <span className="eyebrow text-muted-foreground">Au</span>
            <Input
              type="date"
              aria-label="Date de fin"
              value={to}
              onChange={e => setTo(e.target.value)}
              className="h-10 w-full"
            />
          </div>

          <div className="flex flex-col gap-1.5 sm:flex-1 sm:min-w-48">
            <span className="eyebrow text-muted-foreground">Recherche</span>
            <Input
              value={searchInput}
              onChange={e => setSearchInput(e.target.value)}
              onKeyDown={e => e.key === "Enter" && apply()}
              placeholder="Prénom ou cible…"
              aria-label="Recherche par prénom ou cible"
              className="h-10 w-full"
            />
          </div>

          <div className="flex items-center gap-2">
            <Button variant="navy" onClick={apply} className="flex-1 sm:flex-none">
              Filtrer
            </Button>
            <Button variant="outline" onClick={reset} className="flex-1 sm:flex-none">
              Réinitialiser
            </Button>
          </div>
        </div>

        {data && (
          <p className="text-xs text-muted-foreground mb-3">
            {fmtInt(data.total)} résultat{data.total !== 1 ? "s" : ""}
          </p>
        )}

        {error && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive mb-3">
            {error}
          </div>
        )}

        {/* Table — scrolls horizontally on small screens */}
        <div className="-mx-4 sm:mx-0 overflow-x-auto">
          <table className="w-full min-w-160 text-sm">
            <thead>
              <tr className="border-b border-border text-navy">
                <th className="text-left py-2 px-4 sm:px-2 eyebrow text-navy-500 font-normal">Heure</th>
                <th className="text-left py-2 px-4 sm:px-2 eyebrow text-navy-500 font-normal">Prénom</th>
                <th className="text-left py-2 px-4 sm:px-2 eyebrow text-navy-500 font-normal">Cible</th>
                <th className="text-left py-2 px-4 sm:px-2 eyebrow text-navy-500 font-normal">Statut</th>
                <th className="text-left py-2 px-4 sm:px-2 eyebrow text-navy-500 font-normal">Prompt</th>
                <th className="text-left py-2 px-4 sm:px-2 eyebrow text-navy-500 font-normal">Jetons</th>
              </tr>
            </thead>
            <tbody>
              {loading
                ? Array.from({ length: 10 }, (_, i) => (
                    <tr key={i} className="border-b border-border/60">
                      <td colSpan={6} className="py-2.5 px-4 sm:px-2">
                        <Skeleton className="h-5" />
                      </td>
                    </tr>
                  ))
                : data?.analyses.map(a => (
                    <tr key={a.id} className="border-b border-border/60 last:border-0 hover:bg-muted/40 transition-colors">
                      <td className="py-2.5 px-4 sm:px-2 font-mono text-xs text-muted-foreground whitespace-nowrap">
                        {fmtDateTime(a.created_at)}
                      </td>
                      <td className="py-2.5 px-4 sm:px-2 text-navy font-medium">{a.inputs?.prenom ?? "—"}</td>
                      <td className="py-2.5 px-4 sm:px-2 max-w-50 truncate text-muted-foreground">
                        {a.inputs?.cible_visee ?? "—"}
                      </td>
                      <td className="py-2.5 px-4 sm:px-2">
                        <StatusBadge status={a.status} />
                      </td>
                      <td className="py-2.5 px-4 sm:px-2 font-mono text-xs text-navy">
                        {versionLabel(a.prompt_version_id)}
                      </td>
                      <td className="py-2.5 px-4 sm:px-2 font-mono text-xs text-muted-foreground">
                        {a.tokens_in != null
                          ? fmtInt(a.tokens_in + (a.tokens_out ?? 0))
                          : "—"}
                      </td>
                    </tr>
                  ))}
            </tbody>
          </table>
        </div>

        {/* Empty state */}
        {!loading && data?.analyses.length === 0 && (
          <p className="text-center text-sm text-muted-foreground py-10">
            Aucune analyse trouvée.
          </p>
        )}

        {/* Pagination */}
        {data && data.pages > 1 && (
          <div className="flex items-center gap-3 mt-4 justify-end">
            <Button
              size="sm" variant="outline"
              disabled={page <= 1 || loading}
              onClick={() => goPage(page - 1)}
            >
              Précédent
            </Button>
            <span className="text-xs font-mono text-muted-foreground">
              {page} / {data.pages}
            </span>
            <Button
              size="sm" variant="outline"
              disabled={page >= data.pages || loading}
              onClick={() => goPage(page + 1)}
            >
              Suivant
            </Button>
          </div>
        )}
      </div>
    </>
  )
}

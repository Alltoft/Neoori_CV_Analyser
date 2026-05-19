"use client"

import { useCallback, useEffect, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"
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

export default function AnalysesPage() {
  const [data, setData] = useState<ListResponse | null>(null)
  const [versions, setVersions] = useState<PromptVersion[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [page, setPage] = useState(1)
  const [status, setStatus] = useState("")
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
    setAppliedSearch(searchInput)
    setAppliedFrom(from)
    setAppliedTo(to)
    load(1, status, searchInput, from, to)
  }

  const reset = () => {
    setPage(1); setStatus("")
    setSearchInput(""); setAppliedSearch("")
    setFrom(""); setTo("")
    setAppliedFrom(""); setAppliedTo("")
    load(1, "", "", "", "")
  }

  const goPage = (p: number) => {
    setPage(p)
    load(p, status, appliedSearch, appliedFrom, appliedTo)
  }

  const versionLabel = (id: string | null): string =>
    versions.find(v => v.id === id)?.version_label ?? "—"

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      {/* Filter bar */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <h2 className="font-semibold text-sm mr-2">analyses</h2>
        <Select
          value={status || "tous"}
          onValueChange={v => v !== null && setStatus(v === "tous" ? "" : v)}
        >
          <SelectTrigger className="h-7 text-xs w-36">
            <SelectValue placeholder="tous statuts" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="tous">tous</SelectItem>
            <SelectItem value="success">success</SelectItem>
            <SelectItem value="error">error</SelectItem>
            <SelectItem value="timeout">timeout</SelectItem>
          </SelectContent>
        </Select>
        <Input
          type="date"
          value={from}
          onChange={e => setFrom(e.target.value)}
          className="h-7 text-xs w-36"
        />
        <Input
          type="date"
          value={to}
          onChange={e => setTo(e.target.value)}
          className="h-7 text-xs w-36"
        />
        <Input
          value={searchInput}
          onChange={e => setSearchInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && apply()}
          placeholder="prénom ou cible…"
          className="h-7 text-xs w-44"
        />
        <Button size="sm" className="h-7 text-xs" onClick={apply}>
          filtrer
        </Button>
        <Button size="sm" variant="outline" className="h-7 text-xs" onClick={reset}>
          réinitialiser
        </Button>
        {data && (
          <span className="text-[10px] text-muted-foreground ml-auto">
            {data.total} résultat{data.total !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 mb-3">
          {error}
        </div>
      )}

      {/* Table */}
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-border text-muted-foreground text-[10px] font-mono uppercase">
            <th className="text-left pb-2 pr-3 font-normal">heure</th>
            <th className="text-left pb-2 pr-3 font-normal">prénom</th>
            <th className="text-left pb-2 pr-3 font-normal">cible</th>
            <th className="text-left pb-2 pr-3 font-normal">statut</th>
            <th className="text-left pb-2 pr-3 font-normal">prompt</th>
            <th className="text-left pb-2 font-normal">tokens</th>
          </tr>
        </thead>
        <tbody>
          {loading
            ? Array(10).fill(0).map((_, i) => (
                <tr key={i} className="border-b border-dashed border-border">
                  <td colSpan={6} className="py-2">
                    <Skeleton className="h-5" />
                  </td>
                </tr>
              ))
            : data?.analyses.map(a => (
                <tr key={a.id} className="border-b border-dashed border-border last:border-0">
                  <td className="py-2 pr-3 font-mono text-[10px] text-muted-foreground whitespace-nowrap">
                    {new Date(a.created_at).toLocaleString("fr-FR", {
                      day: "2-digit", month: "2-digit",
                      hour: "2-digit", minute: "2-digit",
                    })}
                  </td>
                  <td className="py-2 pr-3">{a.inputs?.prenom ?? "—"}</td>
                  <td className="py-2 pr-3 max-w-[180px] truncate text-muted-foreground">
                    {a.inputs?.cible_visee ?? "—"}
                  </td>
                  <td className="py-2 pr-3">
                    <Badge
                      variant="outline"
                      className={cn("text-[9px] px-1.5",
                        a.status === "success" ? "bg-green-50 border-green-200 text-green-700" :
                        a.status === "timeout" ? "bg-yellow-50 border-yellow-200 text-yellow-700" :
                        a.status === "running"  ? "bg-blue-50 border-blue-200 text-blue-700" :
                        "bg-red-50 border-red-200 text-red-700"
                      )}
                    >
                      {a.status}
                    </Badge>
                  </td>
                  <td className="py-2 pr-3 font-mono text-[10px]">
                    {versionLabel(a.prompt_version_id)}
                  </td>
                  <td className="py-2 font-mono text-[10px] text-muted-foreground">
                    {a.tokens_in != null
                      ? (a.tokens_in + (a.tokens_out ?? 0)).toLocaleString("fr-FR")
                      : "—"}
                  </td>
                </tr>
              ))}
        </tbody>
      </table>

      {/* Empty state */}
      {!loading && data?.analyses.length === 0 && (
        <p className="text-center text-xs text-muted-foreground py-8">
          aucune analyse trouvée
        </p>
      )}

      {/* Pagination */}
      {data && data.pages > 1 && (
        <div className="flex items-center gap-2 mt-4 justify-end">
          <Button
            size="sm" variant="outline" className="h-7 text-xs"
            disabled={page <= 1 || loading}
            onClick={() => goPage(page - 1)}
          >
            précédent
          </Button>
          <span className="text-[10px] text-muted-foreground">
            {page} / {data.pages}
          </span>
          <Button
            size="sm" variant="outline" className="h-7 text-xs"
            disabled={page >= data.pages || loading}
            onClick={() => goPage(page + 1)}
          >
            suivant
          </Button>
        </div>
      )}
    </div>
  )
}

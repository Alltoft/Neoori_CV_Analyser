"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Separator } from "@/components/ui/separator"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"
import type { PromptVersion } from "@/types"

interface Stats {
  total_analyses: number; success_count: number; error_count: number
  timeout_count: number; success_rate: number; conversion_rate: number
  total_tokens_in: number; total_tokens_out: number
  active_prompt: PromptVersion | null
}
interface LogEntry {
  id: string; created_at: string
  inputs: { prenom?: string; cible_visee?: string } | null
  status: string
}
interface TimeseriesDay { date: string; count: number; tokens: number; free_count: number; paid_count: number }

function MiniSparkline({ data, color = "var(--navy)" }: { data: number[]; color?: string }) {
  if (!data.length) return <div className="h-10 w-full" />
  const max = Math.max(...data, 1)
  const W = 240, H = 40
  const pts = data
    .map((v, i) => `${(i / (data.length - 1)) * W},${H - (v / max) * (H - 4) - 2}`)
    .join(" ")
  return (
    <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`}>
      <polyline points={pts} stroke={color} strokeWidth="1.5" fill="none" strokeLinecap="round" />
    </svg>
  )
}

export default function AdminPage() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [timeseries, setTimeseries] = useState<TimeseriesDay[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      api.get<Stats>("/admin/stats"),
      api.get<{ analyses: LogEntry[] }>("/admin/analyses"),
      api.get<{ days: TimeseriesDay[] }>("/admin/stats/timeseries?days=30"),
    ])
      .then(([s, al, ts]) => {
        setStats(s)
        setLogs(al.analyses.slice(0, 10))
        setTimeseries(ts.days)
      })
      .catch(err => setError(err?.message ?? "Erreur de chargement"))
      .finally(() => setLoading(false))
  }, [])

  const kpis = stats
    ? [
        ["analyses générées", String(stats.total_analyses), "total"],
        ["taux de succès", `${stats.success_rate} %`, `${stats.error_count} erreurs · ${stats.timeout_count} timeouts`],
        ["tokens consommés", `${(stats.total_tokens_in + stats.total_tokens_out).toLocaleString("fr")}`, "entrée + sortie"],
        ["conversion → payant", `${stats.conversion_rate} %`, "sur tous les candidats"],
        ["prompt actif", stats.active_prompt?.version_label ?? "—",
          stats.active_prompt ? `actif depuis le ${new Date(stats.active_prompt.created_at).toLocaleDateString("fr")}` : "aucun"],
      ]
    : []

  if (error) return (
    <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</div>
  )

  return (
    <>
      {/* Page heading */}
      <div className="mb-5">
        <p className="font-mono text-[11px] tracking-[0.15em] uppercase text-orange">Administration</p>
        <h1 className="font-display font-bold text-2xl text-navy mt-1">vue d&apos;ensemble</h1>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-5 gap-3 mb-5">
        {loading
          ? Array(5).fill(0).map((_, i) => <Skeleton key={i} className="h-20 rounded-lg" />)
          : kpis.map(([k, v, d], i) => (
              <div key={String(k)} className="rounded-xl border border-border bg-card p-3">
                <p className="text-[10px] font-mono uppercase tracking-[0.1em] text-muted-foreground">{k}</p>
                <p className={cn("text-2xl font-bold mt-1 text-navy", i === 4 && "text-orange")}>{v}</p>
                <p className="text-[10px] text-muted-foreground mt-0.5">{d}</p>
              </div>
            ))}
      </div>

      <div className="grid grid-cols-[1.4fr_1fr] gap-4">
        {/* Condensed prompt panel */}
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h2 className="font-display font-bold text-sm text-navy">prompt système</h2>
              <p className="text-[10px] text-muted-foreground">versionné · rollback possible</p>
            </div>
            {stats?.active_prompt && (
              <Badge className="bg-orange text-white text-[10px] font-mono">
                {stats.active_prompt.version_label} · ACTIF
              </Badge>
            )}
          </div>
          <Link href="/admin/prompts" className="text-xs font-semibold text-orange hover:underline">
            gérer les prompts →
          </Link>
        </div>

        {/* Condensed analyses log */}
        <div className="rounded-xl border border-border bg-card p-4 overflow-hidden">
          <div className="flex items-baseline justify-between mb-3">
            <h2 className="font-display font-bold text-sm text-navy">analyses récentes</h2>
            <Link href="/admin/analyses" className="text-[10px] font-semibold text-orange hover:underline">
              voir toutes →
            </Link>
          </div>
          <div className="space-y-0">
            {loading
              ? Array(5).fill(0).map((_, i) => (
                  <div key={i} className="py-1.5 border-b border-dashed border-border">
                    <Skeleton className="h-5" />
                  </div>
                ))
              : logs.map(log => (
                  <div key={log.id} className="grid grid-cols-[36px_1fr_52px] gap-2 py-1.5 border-b border-dashed border-border items-center last:border-0">
                    <span className="font-mono text-[10px] text-muted-foreground">
                      {new Date(log.created_at).toLocaleTimeString("fr", { hour: "2-digit", minute: "2-digit" })}
                    </span>
                    <p className="text-xs truncate text-navy">
                      {log.inputs?.prenom ?? "—"} — {log.inputs?.cible_visee?.slice(0, 25) ?? "—"}
                    </p>
                    <Badge
                      variant="outline"
                      className={cn("text-[9px] px-1.5",
                        log.status === "success" ? "bg-success/10 border-success/30 text-success" :
                        log.status === "timeout" ? "bg-peach-soft border-peach text-orange-dark" :
                        "bg-destructive/10 border-destructive/30 text-destructive"
                      )}
                    >
                      {log.status}
                    </Badge>
                  </div>
                ))}
          </div>
        </div>
      </div>

      <Separator className="my-4" />

      {/* Sparklines */}
      <div className="rounded-xl border border-border bg-card p-4 grid grid-cols-3 gap-6">
        {loading
          ? Array(3).fill(0).map((_, i) => <Skeleton key={i} className="h-14" />)
          : (
            <>
              <div>
                <p className="text-[10px] font-mono uppercase tracking-[0.1em] text-muted-foreground mb-2">analyses · 30j</p>
                <MiniSparkline data={timeseries.map(d => d.count)} color="var(--navy)" />
              </div>
              <div>
                <p className="text-[10px] font-mono uppercase tracking-[0.1em] text-muted-foreground mb-2">tokens · 30j</p>
                <MiniSparkline data={timeseries.map(d => d.tokens)} color="var(--orange)" />
              </div>
              <div>
                <p className="text-[10px] font-mono uppercase tracking-[0.1em] text-muted-foreground mb-2">plans payants · 30j</p>
                <MiniSparkline data={timeseries.map(d => d.paid_count)} color="var(--peach)" />
              </div>
            </>
          )}
      </div>
    </>
  )
}

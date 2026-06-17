"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { ArrowRight, FileText, BarChart3 } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { StatCard } from "@/components/ui/stat-card"
import { StatusBadge } from "@/components/ui/status-badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert"
import { Separator } from "@/components/ui/separator"
import { api } from "@/lib/api"
import { fmtInt, fmtCompact, fmtPct, fmtDate } from "@/lib/format"
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

/** Read-only 30-day trend line with an accessible title and a visible last-value label. */
function MiniSparkline({
  data,
  label,
  color = "var(--navy)",
  format = fmtInt,
}: {
  data: number[]
  label: string
  color?: string
  format?: (n?: number | null) => string
}) {
  if (!data.length) return <div className="h-10 w-full" aria-hidden />
  const max = Math.max(...data, 1)
  const W = 240, H = 40
  const pts = data
    .map((v, i) => `${(i / (data.length - 1)) * W},${H - (v / max) * (H - 4) - 2}`)
    .join(" ")
  const last = data[data.length - 1]
  const lastX = W
  const lastY = H - (last / max) * (H - 4) - 2
  return (
    <div className="flex items-end gap-3">
      <svg
        width="100%"
        height={H}
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`${label} : ${format(last)} sur le dernier jour`}
        className="min-w-0 flex-1 overflow-visible"
      >
        <title>{`${label} — ${format(last)} sur le dernier jour`}</title>
        <polyline points={pts} stroke={color} strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx={lastX} cy={lastY} r="2.5" fill={color} />
      </svg>
      <span className="shrink-0 font-mono text-sm font-semibold tabular-nums text-navy" style={{ color }}>
        {format(last)}
      </span>
    </div>
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

  if (error) return (
    <Alert variant="destructive">
      <AlertTitle>Impossible de charger le tableau de bord</AlertTitle>
      <AlertDescription>{error}</AlertDescription>
    </Alert>
  )

  return (
    <div className="space-y-6">
      {/* Page heading */}
      <div>
        <p className="eyebrow text-orange-dark">Administration</p>
        <h1 className="mt-1 font-display text-2xl font-bold text-navy">Vue d&apos;ensemble</h1>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {loading || !stats
          ? Array(5).fill(0).map((_, i) => <Skeleton key={i} className="h-24 rounded-xl" />)
          : (
            <>
              <StatCard
                label="Analyses générées"
                value={fmtInt(stats.total_analyses)}
                hint="Total cumulé"
              />
              <StatCard
                label="Taux de succès"
                value={fmtPct(stats.success_rate)}
                hint={`${fmtInt(stats.error_count)} échecs · ${fmtInt(stats.timeout_count)} expirées`}
              />
              <StatCard
                label="Tokens consommés"
                value={fmtCompact(stats.total_tokens_in + stats.total_tokens_out)}
                hint="Entrée + sortie"
              />
              <StatCard
                label="Conversion → payant"
                value={fmtPct(stats.conversion_rate)}
                hint="Sur tous les candidats"
              />
              <StatCard
                accent
                label="Prompt actif"
                value={stats.active_prompt?.version_label ?? "—"}
                hint={stats.active_prompt
                  ? `Actif depuis le ${fmtDate(stats.active_prompt.created_at)}`
                  : "Aucun prompt actif"}
              />
            </>
          )}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1.4fr_1fr]">
        {/* Condensed prompt panel */}
        <Card size="sm">
          <CardHeader className="flex-row items-start justify-between gap-3">
            <div>
              <CardTitle className="flex items-center gap-2">
                <FileText className="size-4 text-orange" aria-hidden />
                Prompt système
              </CardTitle>
              <CardDescription>Versionné · rollback possible</CardDescription>
            </div>
            {!loading && stats?.active_prompt && (
              <Badge variant="peach" className="font-mono uppercase tracking-wide">
                {stats.active_prompt.version_label} · actif
              </Badge>
            )}
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Le prompt envoyé au modèle est géré dans l&apos;historique versionné, avec auteur,
              horodatage et restauration d&apos;une version antérieure.
            </p>
            <Link
              href="/admin/prompts"
              className="link-underline mt-3 inline-flex items-center gap-1 text-sm font-semibold text-orange-dark focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange/40 rounded-sm"
            >
              Gérer les prompts
              <ArrowRight className="size-4" aria-hidden />
            </Link>
          </CardContent>
        </Card>

        {/* Condensed analyses log (read-only) */}
        <Card size="sm">
          <CardHeader className="flex-row items-center justify-between gap-3">
            <CardTitle>Analyses récentes</CardTitle>
            <Link
              href="/admin/analyses"
              className="link-underline inline-flex items-center gap-1 text-xs font-semibold text-orange-dark focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange/40 rounded-sm"
            >
              Voir toutes
              <ArrowRight className="size-3.5" aria-hidden />
            </Link>
          </CardHeader>
          <CardContent>
            <ul className="divide-y divide-border">
              {loading
                ? Array(5).fill(0).map((_, i) => (
                    <li key={i} className="py-2">
                      <Skeleton className="h-5" />
                    </li>
                  ))
                : logs.length === 0
                  ? <li className="py-3 text-sm text-muted-foreground">Aucune analyse récente.</li>
                  : logs.map(log => (
                      <li
                        key={log.id}
                        className="grid grid-cols-[auto_1fr_auto] items-center gap-3 py-2"
                      >
                        <span className="font-mono text-xs tabular-nums text-muted-foreground">
                          {new Date(log.created_at).toLocaleTimeString("fr", { hour: "2-digit", minute: "2-digit" })}
                        </span>
                        <p className="truncate text-sm text-navy">
                          <span className="font-medium">{log.inputs?.prenom ?? "—"}</span>
                          <span className="text-muted-foreground"> — {log.inputs?.cible_visee?.slice(0, 28) ?? "—"}</span>
                        </p>
                        <StatusBadge status={log.status} className="justify-self-end" />
                      </li>
                    ))}
            </ul>
          </CardContent>
        </Card>
      </div>

      <Separator />

      {/* Sparklines (read-only, 30-day trends) */}
      <Card size="sm">
        <CardHeader className="flex-row items-center gap-2">
          <BarChart3 className="size-4 text-orange" aria-hidden />
          <CardTitle>Tendances sur 30 jours</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-6 sm:grid-cols-3">
          {loading
            ? Array(3).fill(0).map((_, i) => <Skeleton key={i} className="h-16" />)
            : (
              <>
                <div>
                  <p className="eyebrow mb-2 text-muted-foreground">Analyses · 30 j</p>
                  <MiniSparkline data={timeseries.map(d => d.count)} label="Analyses sur 30 jours" color="var(--navy)" format={fmtInt} />
                </div>
                <div>
                  <p className="eyebrow mb-2 text-muted-foreground">Tokens · 30 j</p>
                  <MiniSparkline data={timeseries.map(d => d.tokens)} label="Tokens consommés sur 30 jours" color="var(--orange)" format={fmtCompact} />
                </div>
                <div>
                  <p className="eyebrow mb-2 text-muted-foreground">Plans payants · 30 j</p>
                  <MiniSparkline data={timeseries.map(d => d.paid_count)} label="Plans payants sur 30 jours" color="var(--orange-dark)" format={fmtInt} />
                </div>
              </>
            )}
        </CardContent>
      </Card>
    </div>
  )
}

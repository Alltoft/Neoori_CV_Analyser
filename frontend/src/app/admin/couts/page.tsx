"use client"

import { useEffect, useState } from "react"
import { Skeleton } from "@/components/ui/skeleton"
import { StatCard } from "@/components/ui/stat-card"
import { api } from "@/lib/api"
import { fmtCompact, fmtEur, fmtInt } from "@/lib/format"
import { CircleDollarSign, FileText, Sparkles, Zap } from "lucide-react"

interface CostDay {
  date: string; analyses_count: number
  haiku_tokens_in: number; haiku_tokens_out: number
  sonnet_tokens_in: number; sonnet_tokens_out: number
  cost_eur: number
}
interface CostsResponse {
  days: CostDay[]
  total: {
    analyses_count: number
    haiku_tokens_in: number; haiku_tokens_out: number
    sonnet_tokens_in: number; sonnet_tokens_out: number
    cost_eur: number
  }
}

/** Compute the sonnet (paid) portion of a day's cost, mirroring the table math. */
function sonnetCostOf(d: CostDay) {
  return (d.sonnet_tokens_in * 3 + d.sonnet_tokens_out * 15) / 1_000_000 * 0.92
}

const fmtDayLong = (iso: string) =>
  new Date(iso).toLocaleDateString("fr-FR", { weekday: "short", day: "2-digit", month: "short" })
const fmtDayShort = (iso: string) =>
  new Date(iso).toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit" })

function BarChart({ data }: { data: CostDay[] }) {
  if (!data.length) {
    return (
      <p className="py-10 text-center text-sm text-muted-foreground">
        Aucune donnée sur la période.
      </p>
    )
  }
  const maxCost = Math.max(...data.map(d => d.cost_eur), 0.0001)
  const W = 600, H = 180
  const gap = data.length > 40 ? 1 : 2
  const barW = Math.max(1, W / data.length - gap)

  return (
    <svg
      width="100%"
      viewBox={`0 0 ${W} ${H}`}
      className="overflow-visible"
      role="img"
      aria-label="Coût quotidien estimé sur 30 jours, réparti entre sonnet (payant) et haiku (gratuit)"
    >
      {data.map((d, i) => {
        const totalH = Math.max(0, Math.min((d.cost_eur / maxCost) * (H - 4), H - 2))
        const sonnetCost = sonnetCostOf(d)
        const sonnetH = Math.max(0, Math.min((sonnetCost / maxCost) * (H - 4), totalH))
        const x = i * (W / data.length) + gap / 2
        const tooltip = `${fmtDayLong(d.date)} — ${fmtEur(d.cost_eur)} · ${d.analyses_count} analyse${d.analyses_count > 1 ? "s" : ""}`

        return (
          <g key={d.date}>
            <title>{tooltip}</title>
            {/* full-height hover target so thin bars stay easy to point at */}
            <rect x={x} y={0} width={barW} height={H} fill="transparent" />
            <rect
              x={x} y={H - totalH} width={barW} height={totalH}
              fill="var(--navy)" opacity={0.2} rx={2}
            />
            <rect
              x={x} y={H - sonnetH} width={barW} height={sonnetH}
              fill="var(--orange)" opacity={0.9} rx={2}
            />
          </g>
        )
      })}
    </svg>
  )
}

function Legend() {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
      <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <span
          className="inline-block h-2.5 w-3.5 rounded-sm"
          style={{ background: "var(--orange)", opacity: 0.9 }}
        />
        Sonnet (payant)
      </span>
      <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <span
          className="inline-block h-2.5 w-3.5 rounded-sm"
          style={{ background: "var(--navy)", opacity: 0.2 }}
        />
        Haiku (gratuit)
      </span>
    </div>
  )
}

export default function CoutsPage() {
  const [data, setData] = useState<CostsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.get<CostsResponse>("/admin/costs?days=30")
      .then(setData)
      .catch(err => setError(err?.message ?? "Erreur de chargement"))
      .finally(() => setLoading(false))
  }, [])

  if (error) return (
    <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
      {error}
    </div>
  )

  const t = data?.total

  return (
    <div className="space-y-5">
      {/* Page heading */}
      <div>
        <p className="eyebrow text-orange-dark">Administration</p>
        <h1 className="mt-1 font-display text-2xl font-bold text-navy">Coûts API</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Estimation des dépenses Anthropic sur les 30 derniers jours.
        </p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {loading || !t
          ? Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-28 rounded-xl" />)
          : (
            <>
              <StatCard
                accent
                label="Coût estimé · 30 j"
                value={fmtEur(t.cost_eur)}
                hint="Conversion USD→EUR ≈ 0,92"
                icon={<CircleDollarSign className="size-4" />}
              />
              <StatCard
                label="Analyses"
                value={fmtInt(t.analyses_count)}
                hint="Sur les 30 derniers jours"
                icon={<FileText className="size-4" />}
              />
              <StatCard
                label="Tokens haiku"
                value={fmtCompact(t.haiku_tokens_in + t.haiku_tokens_out)}
                hint="Plan gratuit"
                icon={<Zap className="size-4" />}
              />
              <StatCard
                label="Tokens sonnet"
                value={fmtCompact(t.sonnet_tokens_in + t.sonnet_tokens_out)}
                hint="Plan payant"
                icon={<Sparkles className="size-4" />}
              />
            </>
          )}
      </div>

      {/* Daily bar chart */}
      <div className="rounded-xl bg-card p-5 shadow-soft ring-1 ring-foreground/10">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-display text-sm font-semibold text-navy">Coût quotidien</h2>
            <p className="text-xs text-muted-foreground">30 derniers jours</p>
          </div>
          <Legend />
        </div>
        {loading
          ? <Skeleton className="h-44 w-full rounded-lg" />
          : data && <BarChart data={data.days} />}
      </div>

      {/* Daily breakdown table */}
      <div className="rounded-xl bg-card p-5 shadow-soft ring-1 ring-foreground/10">
        <h2 className="mb-4 font-display text-sm font-semibold text-navy">Détail par jour</h2>
        <div className="-mx-5 overflow-x-auto px-5">
          <table className="w-full min-w-[480px] text-sm">
            <thead>
              <tr className="border-b border-border text-navy">
                <th className="eyebrow pb-2 pr-4 text-left text-muted-foreground">Date</th>
                <th className="eyebrow pb-2 pr-4 text-right text-muted-foreground">Analyses</th>
                <th className="eyebrow pb-2 pr-4 text-right text-muted-foreground">Tok. haiku</th>
                <th className="eyebrow pb-2 pr-4 text-right text-muted-foreground">Tok. sonnet</th>
                <th className="eyebrow pb-2 text-right text-muted-foreground">Coût</th>
              </tr>
            </thead>
            <tbody>
              {loading
                ? Array.from({ length: 7 }, (_, i) => (
                    <tr key={i}><td colSpan={5} className="py-2"><Skeleton className="h-4" /></td></tr>
                  ))
                : data?.days.map(d => (
                    <tr key={d.date} className="border-b border-dashed border-border last:border-0">
                      <td className="py-2 pr-4 font-mono text-xs text-navy">{fmtDayShort(d.date)}</td>
                      <td className="py-2 pr-4 text-right tabular-nums">{fmtInt(d.analyses_count)}</td>
                      <td className="py-2 pr-4 text-right font-mono text-xs tabular-nums">
                        {fmtInt(d.haiku_tokens_in + d.haiku_tokens_out)}
                      </td>
                      <td className="py-2 pr-4 text-right font-mono text-xs tabular-nums">
                        {fmtInt(d.sonnet_tokens_in + d.sonnet_tokens_out)}
                      </td>
                      <td className="py-2 text-right font-mono text-xs tabular-nums text-navy">
                        {fmtEur(d.cost_eur)}
                      </td>
                    </tr>
                  ))}
              {/* Totals row */}
              {!loading && t && (
                <tr className="border-t-2 border-navy/30 font-semibold text-navy">
                  <td className="pt-3 pr-4 text-xs">Total</td>
                  <td className="pt-3 pr-4 text-right tabular-nums">{fmtInt(t.analyses_count)}</td>
                  <td className="pt-3 pr-4 text-right font-mono text-xs tabular-nums">
                    {fmtInt(t.haiku_tokens_in + t.haiku_tokens_out)}
                  </td>
                  <td className="pt-3 pr-4 text-right font-mono text-xs tabular-nums">
                    {fmtInt(t.sonnet_tokens_in + t.sonnet_tokens_out)}
                  </td>
                  <td className="pt-3 text-right font-mono text-xs tabular-nums text-orange-dark">
                    {fmtEur(t.cost_eur)}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

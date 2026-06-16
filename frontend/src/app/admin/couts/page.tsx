"use client"

import { useEffect, useState } from "react"
import { Skeleton } from "@/components/ui/skeleton"
import { api } from "@/lib/api"
import { cn } from "@/lib/utils"

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

function BarChart({ data }: { data: CostDay[] }) {
  if (!data.length) return null
  const maxCost = Math.max(...data.map(d => d.cost_eur), 0.0001)
  const W = 600, H = 72
  const barW = Math.max(1, W / data.length - 2)

  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} className="overflow-visible">
      {data.map((d, i) => {
        const totalH = Math.max(0, Math.min((d.cost_eur / maxCost) * (H - 4), H - 2))
        const sonnetCost =
          (d.sonnet_tokens_in * 3 + d.sonnet_tokens_out * 15) / 1_000_000 * 0.92
        const sonnetH = Math.max(0, Math.min((sonnetCost / maxCost) * (H - 4), totalH))
        const x = i * (W / data.length) + 1

        return (
          <g key={d.date}>
            <rect
              x={x} y={H - totalH} width={barW} height={totalH}
              fill="var(--navy)" opacity={0.18} rx={1}
            />
            <rect
              x={x} y={H - sonnetH} width={barW} height={sonnetH}
              fill="var(--orange)" opacity={0.85} rx={1}
            />
          </g>
        )
      })}
    </svg>
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

  const fmt = (n: number) => n.toLocaleString("fr-FR")

  if (error) return (
    <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</div>
  )

  return (
    <div className="space-y-4">
      {/* Page heading */}
      <div>
        <p className="font-mono text-[11px] tracking-[0.15em] uppercase text-orange">Administration</p>
        <h1 className="font-display font-bold text-2xl text-navy mt-1">coûts API</h1>
      </div>

      {/* Summary strip */}
      <div className="grid grid-cols-4 gap-3">
        {loading
          ? Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-20 rounded-lg" />)
          : data && [
              ["coût estimé · 30j",    `${data.total.cost_eur.toFixed(2)} €`,  "USD → EUR ×0.92 (approx)"],
              ["analyses",             String(data.total.analyses_count),       "total période"],
              ["tokens haiku",         fmt(data.total.haiku_tokens_in + data.total.haiku_tokens_out),   "plan gratuit"],
              ["tokens sonnet",        fmt(data.total.sonnet_tokens_in + data.total.sonnet_tokens_out), "plan payant"],
            ].map(([k, v, d], i) => (
              <div key={String(k)} className="rounded-xl border border-border bg-card p-3">
                <p className="text-[10px] font-mono uppercase tracking-[0.1em] text-muted-foreground">{k}</p>
                <p className={cn("text-2xl font-bold mt-1 text-navy", i === 0 && "text-orange")}>{v}</p>
                <p className="text-[10px] text-muted-foreground mt-0.5">{d}</p>
              </div>
            ))}
      </div>

      {/* Bar chart */}
      <div className="rounded-xl border border-border bg-card p-4">
        <div className="flex items-center gap-4 mb-3">
          <h2 className="font-display font-bold text-sm text-navy">coût quotidien · 30j</h2>
          <span className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
            <span
              className="inline-block w-3 h-2 rounded-sm"
              style={{ background: "var(--orange)", opacity: 0.85 }}
            />
            sonnet (payant)
          </span>
          <span className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
            <span
              className="inline-block w-3 h-2 rounded-sm"
              style={{ background: "var(--navy)", opacity: 0.18 }}
            />
            haiku (gratuit)
          </span>
        </div>
        {loading ? <Skeleton className="h-20" /> : data && <BarChart data={data.days} />}
      </div>

      {/* Daily breakdown table */}
      <div className="rounded-xl border border-border bg-card p-4">
        <h2 className="font-display font-bold text-sm text-navy mb-3">détail par jour</h2>
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-navy/20 text-navy text-[10px] font-mono uppercase tracking-[0.1em]">
              <th className="text-left pb-2 pr-4 font-normal">date</th>
              <th className="text-right pb-2 pr-4 font-normal">analyses</th>
              <th className="text-right pb-2 pr-4 font-normal">tok. haiku</th>
              <th className="text-right pb-2 pr-4 font-normal">tok. sonnet</th>
              <th className="text-right pb-2 font-normal">coût €</th>
            </tr>
          </thead>
          <tbody>
            {loading
              ? Array.from({ length: 7 }, (_, i) => (
                  <tr key={i}><td colSpan={5} className="py-2"><Skeleton className="h-4" /></td></tr>
                ))
              : data?.days.map(d => (
                  <tr key={d.date} className="border-b border-dashed border-border last:border-0">
                    <td className="py-1.5 pr-4 font-mono text-[10px]">
                      {new Date(d.date).toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit" })}
                    </td>
                    <td className="py-1.5 pr-4 text-right">{d.analyses_count}</td>
                    <td className="py-1.5 pr-4 text-right font-mono text-[10px]">
                      {fmt(d.haiku_tokens_in + d.haiku_tokens_out)}
                    </td>
                    <td className="py-1.5 pr-4 text-right font-mono text-[10px]">
                      {fmt(d.sonnet_tokens_in + d.sonnet_tokens_out)}
                    </td>
                    <td className="py-1.5 text-right font-mono text-[10px]">
                      {d.cost_eur.toFixed(4)}
                    </td>
                  </tr>
                ))}
            {/* Totals row */}
            {!loading && data && (
              <tr className="border-t-2 border-navy/30 font-semibold text-navy">
                <td className="pt-2 pr-4 text-[10px]">total</td>
                <td className="pt-2 pr-4 text-right">{data.total.analyses_count}</td>
                <td className="pt-2 pr-4 text-right font-mono text-[10px]">
                  {fmt(data.total.haiku_tokens_in + data.total.haiku_tokens_out)}
                </td>
                <td className="pt-2 pr-4 text-right font-mono text-[10px]">
                  {fmt(data.total.sonnet_tokens_in + data.total.sonnet_tokens_out)}
                </td>
                <td className="pt-2 text-right font-mono text-[10px]">
                  {data.total.cost_eur.toFixed(4)}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

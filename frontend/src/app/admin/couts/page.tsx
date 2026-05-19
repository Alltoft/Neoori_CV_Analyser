"use client"

import { useEffect, useState } from "react"
import { Skeleton } from "@/components/ui/skeleton"
import { api } from "@/lib/api"

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
              fill="var(--foreground)" opacity={0.12} rx={1}
            />
            <rect
              x={x} y={H - sonnetH} width={barW} height={sonnetH}
              fill="hsl(var(--primary))" opacity={0.65} rx={1}
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
    <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
  )

  return (
    <div className="space-y-4">
      {/* Summary strip */}
      <div className="grid grid-cols-4 gap-3">
        {loading
          ? Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-20 rounded-lg" />)
          : data && [
              ["coût estimé · 30j",    `${data.total.cost_eur.toFixed(2)} €`,  "USD → EUR ×0.92 (approx)"],
              ["analyses",             String(data.total.analyses_count),       "total période"],
              ["tokens haiku",         fmt(data.total.haiku_tokens_in + data.total.haiku_tokens_out),   "plan gratuit"],
              ["tokens sonnet",        fmt(data.total.sonnet_tokens_in + data.total.sonnet_tokens_out), "plan payant"],
            ].map(([k, v, d]) => (
              <div key={String(k)} className="rounded-lg border border-border bg-card p-3">
                <p className="text-[10px] font-mono uppercase text-muted-foreground">{k}</p>
                <p className="text-2xl font-bold mt-1">{v}</p>
                <p className="text-[10px] text-muted-foreground mt-0.5">{d}</p>
              </div>
            ))}
      </div>

      {/* Bar chart */}
      <div className="rounded-lg border border-border bg-card p-4">
        <div className="flex items-center gap-4 mb-3">
          <h2 className="font-semibold text-sm">coût quotidien · 30j</h2>
          <span className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
            <span
              className="inline-block w-3 h-2 rounded-sm"
              style={{ background: "hsl(var(--primary))", opacity: 0.65 }}
            />
            sonnet (payant)
          </span>
          <span className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
            <span
              className="inline-block w-3 h-2 rounded-sm"
              style={{ background: "var(--foreground)", opacity: 0.12 }}
            />
            haiku (gratuit)
          </span>
        </div>
        {loading ? <Skeleton className="h-20" /> : data && <BarChart data={data.days} />}
      </div>

      {/* Daily breakdown table */}
      <div className="rounded-lg border border-border bg-card p-4">
        <h2 className="font-semibold text-sm mb-3">détail par jour</h2>
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border text-muted-foreground text-[10px] font-mono uppercase">
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
              <tr className="border-t-2 border-border font-semibold">
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

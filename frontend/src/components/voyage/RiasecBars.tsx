"use client"

import { cn } from "@/lib/utils"
import { RIASEC_ROWS } from "@/lib/voyage-labels"
import type { RiasecScore } from "@/types/voyage"

/**
 * The counselor manual's page-18 block « Profil RIASEC — Barres de
 * visualisation »: one bar per letter, filled to score / max.
 *
 * The maxima come from the payload, never from a literal. The manual prints
 * E 10 and C 10; the bank computes them from the option table and gets E 11 and
 * C 9 (spec erratum 17), which is what the bar has to divide by. The top three
 * letters are marked because the restitution guide's phase 4 asks the counselor
 * to name exactly those three out loud.
 *
 * COUNSELOR SURFACE ONLY — this draws scores and framework letters.
 */
export function RiasecBars({ riasec }: { riasec: RiasecScore }) {
  const top = new Set(riasec.top3.map((t) => t.letter))

  return (
    <ol className="space-y-1.5">
      {RIASEC_ROWS.map(({ letter, univers }) => {
        const score = riasec.scores[letter] ?? 0
        const max = riasec.maxima[letter] ?? 0
        const pct = max > 0 ? Math.round((score / max) * 100) : 0
        const isTop = top.has(letter)

        return (
          <li
            key={letter}
            className="grid grid-cols-[1.25rem_6.5rem_1fr_3.25rem] items-center gap-2"
          >
            <span
              className={cn(
                "font-mono text-xs font-bold",
                isTop ? "text-orange-dark" : "text-muted-foreground",
              )}
            >
              {letter}
            </span>
            <span
              className={cn(
                "truncate text-xs",
                isTop ? "font-semibold text-navy" : "text-muted-foreground",
              )}
            >
              {univers}
            </span>
            <span
              className="block h-2 w-full overflow-hidden rounded-full bg-secondary"
              aria-hidden="true"
            >
              <span
                className={cn(
                  "block h-full rounded-full",
                  isTop ? "bg-orange" : "bg-navy-500/45",
                )}
                style={{ width: `${pct}%` }}
              />
            </span>
            <span className="text-right font-mono text-xs tabular-nums text-navy">
              {score} / {max}
            </span>
          </li>
        )
      })}
    </ol>
  )
}

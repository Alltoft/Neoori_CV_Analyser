"use client"

import Link from "next/link"
import { Check, Lock } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { sessionLock, type BankSession, type Voyage } from "@/types/voyage"

/**
 * The six stamps. One row per session: where the person is, what the cahier
 * calls it, and either a way in or the reason there is not one.
 *
 * A locked row must never render a disabled button — a dead control tells
 * nobody anything. It renders LOCK_CODE / LOCK_PROFILE / LOCK_ORDER, the same
 * strings the API returns on a 403, and the hub puts the remedy next to it.
 */
export function SessionProgress({
  sessions,
  voyage,
  profile,
  answered,
}: {
  sessions: BankSession[]
  voyage: Voyage
  profile: { prenom?: string | null; tranche_age?: string | null } | null
  /** session id -> how many of that session's items already have an answer */
  answered: Record<string, number>
}) {
  return (
    <ol className="space-y-2">
      {sessions.map((s) => {
        const done = (voyage.sessions_completed as string[]).includes(s.n)
        const lock = done ? null : sessionLock(voyage, profile, s.n)
        const count = answered[s.n] ?? 0
        const total = s.items.length

        return (
          <li
            key={s.n}
            className={cn(
              "flex flex-col gap-3 rounded-2xl p-4 ring-1 ring-foreground/10 sm:flex-row sm:items-center",
              done ? "bg-secondary/70" : "bg-card shadow-soft",
            )}
          >
            <span
              className={cn(
                "grid size-9 shrink-0 place-items-center rounded-xl font-mono text-sm font-bold",
                done
                  ? "bg-navy text-peach"
                  : lock
                    ? "bg-secondary text-muted-foreground"
                    : "bg-peach-soft text-orange-dark",
              )}
              aria-hidden
            >
              {done ? <Check className="size-4" /> : s.n}
            </span>

            <div className="min-w-0 flex-1">
              <p className="font-display text-sm font-semibold text-navy">{s.title}</p>
              <p className="text-xs leading-snug text-muted-foreground">{s.subtitle}</p>
              <p className="mt-0.5 font-mono text-[11px] text-muted-foreground">
                {s.duration}
                {!done && count > 0 ? ` · ${count} / ${total} enregistrées` : ""}
              </p>
            </div>

            {done ? (
              <Link
                href={`/voyage/session/${s.n}`}
                className="link-underline shrink-0 self-start text-xs text-navy sm:self-auto"
              >
                Revoir mes réponses
              </Link>
            ) : lock ? (
              <span className="inline-flex shrink-0 items-center gap-1.5 self-start rounded-full bg-secondary px-2.5 py-1 text-[11px] font-medium text-muted-foreground sm:self-auto">
                <Lock className="size-3" aria-hidden /> {lock}
              </span>
            ) : (
              <Button render={<Link href={`/voyage/session/${s.n}`} />} size="lg" className="shrink-0">
                {count > 0 ? "Reprendre" : "Commencer"}
              </Button>
            )}
          </li>
        )
      })}
    </ol>
  )
}

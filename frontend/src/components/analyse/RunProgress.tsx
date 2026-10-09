"use client"

import { useEffect, useRef, useState } from "react"
import Link from "next/link"
import { Progress } from "@/components/ui/progress"
import { Button } from "@/components/ui/button"
import { Logo, InfinityMark } from "@/components/brand/Logo"
import { CheckCircle2, Circle, ArrowLeft, RotateCw } from "lucide-react"
import { cn } from "@/lib/utils"
import { ApiError } from "@/lib/api"
import type { Analysis } from "@/types"

// Steps are keyed on the percentage the backend reports, not on a stopwatch:
// `at` is the progress value at which the step becomes the active one.
const STEPS: { label: string; at: number }[] = [
  { label: "Lecture du parcours",    at: 0  },
  { label: "Analyse du profil",      at: 4  },
  { label: "Rédaction du rapport",   at: 12 },
  { label: "Finalisation",           at: 90 },
]

// Fallback only — used when the backend sends no `progress` (older image).
// Asymptotic on purpose: the old screen filled to 95 % in 48 s and then sat
// there, and a real run takes 84 s on the free tier and 119 s on the paid one.
const ESTIMATED_TOTAL = 60000
const FALLBACK_CEILING = 95

const POLL_INTERVAL_MS = 2000
const POLL_BACKOFF_MS  = 4000   // on network blip
const POLL_MAX_MS      = 10 * 60 * 1000   // give up after 10 min; a mailed run stops there, the mail takes over
const STALLED_POLL_MS  = 30_000   // past the give-up, a run with no mail is still watched, slowly

const EASE_INTERVAL_MS = 120    // bar catches up to the reported value

// What to promise on the eyebrow, per plan. Measured end-to-end on parcours 1.
const DURATION_HINT: Record<string, string> = {
  free: "~1 min 30", haiku: "~1 min 30",
  paid: "~2 min",    sonnet: "~2 min",
  premium: "~3 min",
}

type StepState = "done" | "active" | "wait"

/** The waiting screen of a run: steps, a progress bar fed by the row itself,
 *  and the failure and give-up cards. One screen for the owner's page and the
 *  no-login page (four-doors spec) — the page decides how a row is fetched,
 *  where a finished run goes, and whether a mail is promised. */
export function RunProgress({
  load,
  onDone,
  mailed,
  onRestart,
  onRelaunch,
}: {
  /** Fetch the row once; RunProgress polls it. */
  load: () => Promise<Analysis>
  /** Called once, on success, with the finished row. */
  onDone: (analysis: Analysis) => void
  /** An account is mailed when the run ends; a no-login run is not. */
  mailed: boolean
  /** « Nouvelle analyse » after a failure. */
  onRestart: () => void
  /** A failed promo run is relaunched, not restarted (spec decision 49):
   *  given, and the failed row's door is "promo", the error card's button
   *  reads « Relancer » and calls this instead of onRestart. */
  onRelaunch?: () => Promise<unknown>
}) {
  const [progress,   setProgress]   = useState(0)   // what the bar renders
  const [done,       setDone]        = useState(false)
  const [error,      setError]       = useState<string | null>(null)
  // The row that ended in error or timeout: its door decides whether the card
  // offers « Relancer » or « Nouvelle analyse ».
  const [failed,     setFailed]      = useState<Analysis | null>(null)
  const [relaunching, setRelaunching] = useState(false)
  const [relaunchError, setRelaunchError] = useState<string | null>(null)
  // Bumped by « Relancer »: the polling effect depends on it, so a relaunch
  // starts a new watch of the same row.
  const [round,      setRound]       = useState(0)
  // A run past POLL_MAX_MS may still finish, and a mailed one says so by mail;
  // the page stops watching it. A run with no mail (`mailed` false) is the only
  // place its result can appear, so there the page keeps watching, slowly. Not
  // an error either way, so not « n'a pas abouti ».
  const [stalled,    setStalled]     = useState(false)
  const [hint,       setHint]        = useState<string | null>(null)
  const [elapsed,    setElapsed]     = useState(0)
  // Set when a watch starts, in the effect: the clock is not read during render.
  const startRef  = useRef(0)
  // Last value reported by the backend. The bar eases towards it rather than
  // jumping, so a 2 s poll interval still reads as continuous movement.
  const targetRef = useRef(0)
  // The latest callbacks, read by the polling loop without restarting it.
  const loadRef = useRef(load)
  const doneRef = useRef(onDone)
  const mailedRef = useRef(mailed)
  useEffect(() => {
    loadRef.current = load
    doneRef.current = onDone
    mailedRef.current = mailed
  })

  useEffect(() => {
    let alive = true
    let timer: ReturnType<typeof setTimeout> | null = null
    startRef.current = Date.now()

    const schedule = (ms: number, fn: () => void) => {
      timer = setTimeout(fn, ms)
    }

    // Backends without the `progress` column: an asymptotic curve on elapsed
    // time. It slows down instead of hitting a ceiling and stopping dead.
    const fallbackPct = () =>
      FALLBACK_CEILING * (1 - Math.exp(-(Date.now() - startRef.current) / ESTIMATED_TOTAL))

    const poll = async () => {
      if (!alive) return
      // Read before the fetch, acted on after it: a tab resumed from sleep
      // past the deadline still asks the server first, so a run that finished
      // meanwhile opens its report instead of « C’est plus long que prévu ».
      const overdue = Date.now() - startRef.current > POLL_MAX_MS
      // Past the deadline the page says « C’est plus long que prévu ». A mailed
      // run stops watching there; one with no mail keeps going, so what the
      // page tells the person to wait for can still arrive.
      const giveUp = () => {
        setStalled(true)
        if (!mailedRef.current) schedule(STALLED_POLL_MS, poll)
      }
      try {
        const analysis = await loadRef.current()
        if (!alive) return
        const { status, progress: reported, inputs } = analysis
        setHint(DURATION_HINT[inputs?._tier ?? ""] ?? null)

        if (status === "success") {
          // A success seen after the give-up: the steps card comes back, all
          // done, for the moment before the report opens.
          setStalled(false)
          setDone(true)
          targetRef.current = 100
          setProgress(100)
          schedule(800, () => doneRef.current(analysis))
          return
        }
        if (status === "error") {
          setFailed(analysis)
          setError("Une erreur est survenue. Veuillez réessayer.")
          return
        }
        if (status === "timeout") {
          setFailed(analysis)
          setError("L'analyse a expiré. Veuillez réessayer.")
          return
        }
        // queued | running → keep polling, until this page has watched long enough
        if (overdue) {
          giveUp()
          return
        }
        const pct = typeof reported === "number" ? reported : fallbackPct()
        targetRef.current = Math.max(targetRef.current, pct)
        schedule(POLL_INTERVAL_MS, poll)
      } catch {
        if (!alive) return
        // Still unreachable past the deadline: give up, as above.
        if (overdue) {
          giveUp()
          return
        }
        // Transient network/proxy blip — back off and retry rather than fail loud
        schedule(POLL_BACKOFF_MS, poll)
      }
    }
    poll()

    const tick = setInterval(() => {
      setElapsed(Date.now() - startRef.current)
      setProgress(prev => {
        const target = targetRef.current
        if (prev >= target) return prev
        return Math.min(target, prev + Math.max(0.25, (target - prev) * 0.1))
      })
    }, EASE_INTERVAL_MS)

    return () => {
      alive = false
      if (timer) clearTimeout(timer)
      clearInterval(tick)
    }
  }, [round])

  const canRelaunch = onRelaunch !== undefined && failed?.door === "promo"

  const relaunch = async () => {
    if (!onRelaunch || relaunching) return
    setRelaunching(true)
    setRelaunchError(null)
    try {
      await onRelaunch()
    } catch (e) {
      setRelaunchError(e instanceof ApiError ? e.message : "Erreur inattendue.")
      setRelaunching(false)
      return
    }
    // The same row is queued again: the bar starts over and the watch with it.
    setError(null)
    setStalled(false)
    setFailed(null)
    targetRef.current = 0
    setProgress(0)
    setElapsed(0)
    setRelaunching(false)
    setRound((r) => r + 1)
  }

  const activeStep = Math.max(0, STEPS.findLastIndex(s => progress >= s.at))

  const stepState = (i: number): StepState => {
    if (i < activeStep) return "done"
    if (i === activeStep) return "active"
    return "wait"
  }

  return (
    <div className="bg-mesh relative flex min-h-screen items-center justify-center overflow-hidden px-5 py-12 sm:px-8">
      <div className="w-full max-w-[540px] animate-fade-up">
        <div className="mb-8 flex justify-center">
          <Logo className="text-2xl" priority />
        </div>

        <div className="mb-8 text-center">
          <p className="eyebrow mb-4 inline-flex items-center gap-2 text-orange-dark">
            <InfinityMark animate={!error && !stalled} className="h-[1.2em]" />
            {error
              ? "Analyse interrompue"
              : `Analyse en cours${hint && !stalled ? ` · ${hint}` : ""}`}
          </p>
          <h1 className="font-display text-3xl font-bold tracking-tight text-navy">
            {error
              ? "L’analyse n’a pas abouti"
              : stalled
                ? "C’est plus long que prévu"
                : "Analyse en cours"}
          </h1>
          <p className="mx-auto mt-2 max-w-sm text-sm text-muted-foreground">
            {error
              ? "Vous pouvez relancer une analyse, vos informations sont conservées."
              : stalled
                ? mailed
                  ? "Vous recevrez un email dès qu’elle sera prête."
                  : "Gardez ce lien : le rapport s’affichera ici dès qu’il sera prêt."
                : "Nous lisons votre profil et préparons votre rapport."}
          </p>
        </div>

        {error ? (
          <div className="rounded-2xl border border-destructive/30 bg-card p-6 text-center shadow-card sm:p-8">
            <p className="mb-5 text-sm text-destructive">{error}</p>
            {relaunchError && <p className="mb-5 text-sm text-destructive">{relaunchError}</p>}
            {canRelaunch ? (
              <Button variant="navy" size="lg" disabled={relaunching} onClick={relaunch}>
                <RotateCw className="size-4" />
                Relancer
              </Button>
            ) : (
              <Button variant="navy" size="lg" onClick={onRestart}>
                <ArrowLeft className="size-4" />
                Nouvelle analyse
              </Button>
            )}
          </div>
        ) : stalled ? (
          mailed ? (
            <div className="rounded-2xl border border-border bg-card p-6 text-center shadow-card sm:p-8">
              {/* Not « Nouvelle analyse »: the first run may still be going, and
                  a second would cost a second generation. */}
              <Button render={<Link href="/espace" />} variant="navy" size="lg">
                <ArrowLeft className="size-4" />
                Retour à mon espace
              </Button>
            </div>
          ) : null
        ) : (
          <div className="rounded-2xl border border-border bg-card p-6 shadow-card sm:p-8">
            <ol className="mb-7 space-y-0">
              {STEPS.map((step, i) => {
                const state = done ? "done" : stepState(i)
                return (
                  <li
                    key={step.label}
                    className="flex items-center gap-3 border-b border-dashed border-border py-3 last:border-0"
                  >
                    <span className="shrink-0">
                      {state === "done" ? (
                        <CheckCircle2 className="size-5 text-success" />
                      ) : (
                        <Circle
                          className={cn(
                            "size-5",
                            state === "active" ? "animate-pulse text-orange" : "text-muted-foreground/35",
                          )}
                        />
                      )}
                    </span>
                    <span
                      className={cn(
                        "flex-1 text-sm",
                        state === "active" && "font-medium text-navy",
                        state === "done" && "text-navy",
                        state === "wait" && "text-muted-foreground/55",
                      )}
                    >
                      {step.label}
                    </span>
                    {state === "active" && (
                      <span className="font-mono text-[11px] tabular-nums text-orange-dark">
                        {(elapsed / 1000).toFixed(1)} s
                      </span>
                    )}
                  </li>
                )
              })}
            </ol>

            <div>
              <div className="mb-2 flex items-center justify-between">
                <span className="eyebrow text-muted-foreground">Progression</span>
                <span className="font-mono text-xs tabular-nums text-orange-dark">
                  {Math.round(progress)} %
                </span>
              </div>
              <Progress value={progress} className="h-2" />
              <p className="mt-4 text-center text-[12px] leading-relaxed text-muted-foreground">
                {mailed
                  ? "Le rapport s’affiche ici automatiquement. Vous recevrez un email quand il sera prêt — vous pouvez fermer cette page."
                  : "Le rapport s’affiche ici automatiquement. Gardez ce lien pour le retrouver."}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

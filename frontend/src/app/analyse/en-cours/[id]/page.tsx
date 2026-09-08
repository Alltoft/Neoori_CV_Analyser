"use client"

import { useEffect, useRef, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { Progress } from "@/components/ui/progress"
import { Button } from "@/components/ui/button"
import { Logo, InfinityMark } from "@/components/brand/Logo"
import { CheckCircle2, Circle, ArrowLeft } from "lucide-react"
import { cn } from "@/lib/utils"
import { api } from "@/lib/api"
import type { Analysis } from "@/types"

// Steps are keyed on the percentage the backend reports, not on a stopwatch:
// `at` is the progress value at which the step becomes the active one.
const STEPS: { label: string; at: number }[] = [
  { label: "Lecture du CV",          at: 0  },
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
const POLL_MAX_MS      = 10 * 60 * 1000   // give up after 10 min total

const EASE_INTERVAL_MS = 120    // bar catches up to the reported value

// What to promise on the eyebrow, per plan. Measured end-to-end on parcours 1.
const DURATION_HINT: Record<string, string> = {
  free: "~1 min 30", haiku: "~1 min 30",
  paid: "~2 min",    sonnet: "~2 min",
  premium: "~3 min",
}

type StepState = "done" | "active" | "wait"

export default function EnCoursPage() {
  const { id } = useParams<{ id: string }>()
  const router  = useRouter()
  const [progress,   setProgress]   = useState(0)   // what the bar renders
  const [done,       setDone]        = useState(false)
  const [error,      setError]       = useState<string | null>(null)
  const [hint,       setHint]        = useState<string | null>(null)
  const [elapsed,    setElapsed]     = useState(0)
  const startRef  = useRef(Date.now())
  // Last value reported by the backend. The bar eases towards it rather than
  // jumping, so a 2 s poll interval still reads as continuous movement.
  const targetRef = useRef(0)

  useEffect(() => {
    let alive = true
    let timer: ReturnType<typeof setTimeout> | null = null

    const schedule = (ms: number, fn: () => void) => {
      timer = setTimeout(fn, ms)
    }

    // Backends without the `progress` column: an asymptotic curve on elapsed
    // time. It slows down instead of hitting a ceiling and stopping dead.
    const fallbackPct = () =>
      FALLBACK_CEILING * (1 - Math.exp(-(Date.now() - startRef.current) / ESTIMATED_TOTAL))

    const poll = async () => {
      if (!alive) return
      if (Date.now() - startRef.current > POLL_MAX_MS) {
        setError("L'analyse a expiré. Veuillez réessayer.")
        return
      }
      try {
        const res = await api.get<{ analysis: Analysis }>(`/analyses/${id}`)
        if (!alive) return
        const { status, progress: reported, inputs } = res.analysis
        setHint(DURATION_HINT[inputs?._tier ?? ""] ?? null)

        if (status === "success") {
          setDone(true)
          targetRef.current = 100
          setProgress(100)
          schedule(800, () => router.push(`/analyse/${id}/rapport`))
          return
        }
        if (status === "error") {
          setError("Une erreur est survenue. Veuillez réessayer.")
          return
        }
        if (status === "timeout") {
          setError("L'analyse a expiré. Veuillez réessayer.")
          return
        }
        // queued | running → keep polling
        const pct = typeof reported === "number" ? reported : fallbackPct()
        targetRef.current = Math.max(targetRef.current, pct)
        schedule(POLL_INTERVAL_MS, poll)
      } catch {
        if (!alive) return
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
  }, [id, router])

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
            <InfinityMark animate={!error} className="h-[1.2em]" />
            {error
              ? "Analyse interrompue"
              : `Analyse en cours${hint ? ` · ${hint}` : ""}`}
          </p>
          <h1 className="font-display text-3xl font-bold tracking-tight text-navy">
            {error ? "L’analyse n’a pas abouti" : "Analyse en cours"}
          </h1>
          <p className="mx-auto mt-2 max-w-sm text-sm text-muted-foreground">
            {error
              ? "Vous pouvez relancer une analyse, vos informations sont conservées."
              : "Nous lisons votre profil et préparons votre rapport."}
          </p>
        </div>

        {error ? (
          <div className="rounded-2xl border border-destructive/30 bg-card p-6 text-center shadow-card sm:p-8">
            <p className="mb-5 text-sm text-destructive">{error}</p>
            <Button
              variant="navy"
              size="lg"
              onClick={() => router.push(`/analyse/nouveau`)}
            >
              <ArrowLeft className="size-4" />
              Nouvelle analyse
            </Button>
          </div>
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
                Laissez cet onglet ouvert, le rapport s’affiche automatiquement.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

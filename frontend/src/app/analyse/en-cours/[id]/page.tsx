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

const STEPS: { label: string; t: number }[] = [
  { label: "Lecture du CV",          t: 0     },
  { label: "Analyse du profil",      t: 12000 },
  { label: "Rédaction du rapport",   t: 24000 },
  { label: "Finalisation",           t: 36000 },
]
const ESTIMATED_TOTAL = 48000
const POLL_INTERVAL_MS = 2000
const POLL_BACKOFF_MS  = 4000   // on network blip
const POLL_MAX_MS      = 10 * 60 * 1000   // give up after 10 min total

type StepState = "done" | "active" | "wait"

export default function EnCoursPage() {
  const { id } = useParams<{ id: string }>()
  const router  = useRouter()
  const [activeStep, setActiveStep] = useState(0)
  const [progress,   setProgress]   = useState(0)
  const [done,       setDone]        = useState(false)
  const [error,      setError]       = useState<string | null>(null)
  const startRef = useRef(Date.now())

  useEffect(() => {
    let alive = true
    let timer: ReturnType<typeof setTimeout> | null = null

    const schedule = (ms: number, fn: () => void) => {
      timer = setTimeout(fn, ms)
    }

    const poll = async () => {
      if (!alive) return
      if (Date.now() - startRef.current > POLL_MAX_MS) {
        setError("L'analyse a expiré. Veuillez réessayer.")
        return
      }
      try {
        const res = await api.get<{ analysis: Analysis }>(`/analyses/${id}`)
        if (!alive) return
        const status = res.analysis.status
        if (status === "success") {
          setDone(true)
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
        schedule(POLL_INTERVAL_MS, poll)
      } catch {
        if (!alive) return
        // Transient network/proxy blip — back off and retry rather than fail loud
        schedule(POLL_BACKOFF_MS, poll)
      }
    }
    poll()

    // Progress animation keyed on elapsed time
    const tick = setInterval(() => {
      const elapsed = Date.now() - startRef.current
      const pct = Math.min((elapsed / ESTIMATED_TOTAL) * 100, 95)
      setProgress(pct)

      const next = STEPS.findLastIndex(s => elapsed >= s.t)
      setActiveStep(Math.max(0, next))
    }, 200)

    return () => {
      alive = false
      if (timer) clearTimeout(timer)
      clearInterval(tick)
    }
  }, [id, router])

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
            {error ? "Analyse interrompue" : "Analyse en cours · ~45 s"}
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
                        {((Date.now() - startRef.current) / 1000).toFixed(1)} s
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

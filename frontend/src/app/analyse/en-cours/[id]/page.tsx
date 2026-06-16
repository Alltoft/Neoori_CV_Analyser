"use client"

import { useEffect, useRef, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { Progress } from "@/components/ui/progress"
import { Logo, InfinityMark } from "@/components/brand/Logo"
import { CheckCircle2, Circle, Lock, ArrowLeft } from "lucide-react"
import { cn } from "@/lib/utils"
import { api } from "@/lib/api"
import type { Analysis } from "@/types"

const STEPS: { label: string; t: number; locked?: boolean }[] = [
  { label: "Lecture du parcours…",          t: 0     },
  { label: "Identification des forces…",    t: 8000  },
  { label: "Analyse des écarts…",           t: 16000 },
  { label: "Rédaction des préconisations…", t: 24000 },
  { label: "Réécriture du CV…",             t: 32000 },
  { label: "Relecture en 3 passes…",        t: 40000 },
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
    <div className="min-h-screen bg-background flex items-center justify-center px-4 relative overflow-hidden">
      {/* ── Ambient brand gradient ── */}
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute -top-32 -right-24 h-[480px] w-[480px] rounded-full bg-orange/12 blur-[120px]" />
        <div className="absolute -bottom-32 -left-32 h-[420px] w-[420px] rounded-full bg-peach/22 blur-[120px]" />
      </div>

      <div className="w-full max-w-[520px] animate-fade-up">
        <div className="flex justify-center mb-7">
          <Logo className="text-2xl" />
        </div>

        <div className="text-center mb-8">
          <p className="inline-flex items-center gap-2 font-mono text-[11px] tracking-[0.15em] uppercase text-orange mb-3">
            <InfinityMark animate={!error} className="h-[1.1em]" />
            EN COURS · ~45 SEC
          </p>
          <h1 className="text-3xl font-bold tracking-tight text-navy">Analyse en cours…</h1>
          <p className="mt-1.5 text-sm text-muted-foreground">
            neoori lit votre profil et prépare votre rapport personnalisé.
          </p>
        </div>

        {error ? (
          <div className="rounded-xl border border-destructive/40 bg-destructive/5 p-6 text-center">
            <p className="text-sm text-destructive mb-4">{error}</p>
            <button onClick={() => router.push(`/analyse/nouveau`)}
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-orange hover:text-orange-dark transition-colors">
              <ArrowLeft className="h-3.5 w-3.5" />
              Nouvelle analyse
            </button>
          </div>
        ) : (
          <div className="rounded-xl border border-border bg-card p-6">
            <div className="space-y-0 mb-6">
              {STEPS.map((step, i) => {
                const state = done ? "done" : stepState(i)
                return (
                  <div key={step.label}
                    className="flex items-center gap-3 py-2.5 border-b border-dashed border-border last:border-0">
                    <span className="shrink-0">
                      {state === "done" ? (
                        <CheckCircle2 className="h-4 w-4 text-success" />
                      ) : step.locked ? (
                        <Lock className="h-4 w-4 text-muted-foreground/40" />
                      ) : (
                        <Circle className={cn("h-4 w-4", state === "active" ? "text-orange" : "text-muted-foreground/40")} />
                      )}
                    </span>
                    <span className={cn(
                      "text-sm flex-1",
                      state === "active" && "font-medium text-navy italic",
                      state === "done" && "text-navy",
                      (state === "wait" || step.locked) && "text-muted-foreground/50",
                    )}>
                      {step.label}
                    </span>
                    {step.locked && (
                      <span className="inline-flex items-center rounded-full bg-secondary px-2 py-0.5 text-[10px] font-mono uppercase tracking-wide text-muted-foreground">
                        payant
                      </span>
                    )}
                    {state === "active" && !step.locked && (
                      <span className="text-[10px] font-mono text-orange tabular-nums">
                        {((Date.now() - startRef.current) / 1000).toFixed(1)} s
                      </span>
                    )}
                  </div>
                )
              })}
            </div>

            <div>
              <div className="flex justify-between text-[10px] font-mono uppercase tracking-wide text-muted-foreground mb-1.5">
                <span>PROGRESSION</span>
                <span className="text-orange tabular-nums">{Math.round(progress)} %</span>
              </div>
              <Progress value={progress} className="h-2" />
              <p className="text-[11px] text-center text-muted-foreground mt-3">
                vous pouvez fermer cet onglet — on vous prévient par e-mail
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

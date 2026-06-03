"use client"

import { useEffect, useRef, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { Progress } from "@/components/ui/progress"
import { Badge } from "@/components/ui/badge"
import { CheckCircle2, Circle, Lock } from "lucide-react"
import { cn } from "@/lib/utils"
import { api } from "@/lib/api"
import type { Analysis } from "@/types"

const STEPS = [
  { label: "lecture du CV",                       t: 0   },
  { label: "cadrage sectoriel · cible identifiée", t: 7000  },
  { label: "lecture stratégique du parcours",      t: 13000 },
  { label: "forces · compétences transférables",   t: 22000 },
  { label: "angles morts · préconisations",        t: 30000 },
  { label: "proposition de CV retravaillé",        t: 38000, locked: true },
]
const ESTIMATED_TOTAL = 45000
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
    <div className="min-h-screen bg-background flex items-center justify-center px-4">
      <div className="w-full max-w-[520px]">
        <div className="text-center mb-8">
          <Badge variant="outline" className="font-mono text-xs mb-3">EN COURS · ~40 SEC</Badge>
          <h1 className="text-3xl font-bold tracking-tight">neoori vous lit.</h1>
          <p className="mt-1.5 text-xs text-muted-foreground font-mono">
            prompt système v1.3 · claude-sonnet-4 · max 4 000 tokens
          </p>
        </div>

        {error ? (
          <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-5 text-center">
            <p className="text-sm text-destructive mb-3">{error}</p>
            <button onClick={() => router.push(`/analyse/nouveau`)}
              className="text-xs underline text-muted-foreground hover:text-foreground">
              ← Nouvelle analyse
            </button>
          </div>
        ) : (
          <>
            <div className="space-y-0 mb-6">
              {STEPS.map((step, i) => {
                const state = done ? "done" : stepState(i)
                return (
                  <div key={step.label}
                    className="flex items-center gap-3 py-2.5 border-b border-dashed border-border last:border-0">
                    <span className="shrink-0">
                      {state === "done" ? (
                        <CheckCircle2 className="h-4 w-4 text-primary" />
                      ) : step.locked ? (
                        <Lock className="h-4 w-4 text-muted-foreground/40" />
                      ) : (
                        <Circle className={cn("h-4 w-4", state === "active" ? "text-foreground" : "text-muted-foreground/40")} />
                      )}
                    </span>
                    <span className={cn(
                      "text-sm flex-1",
                      state === "active" && "italic",
                      (state === "wait" || step.locked) && "text-muted-foreground/50",
                    )}>
                      {step.label}
                    </span>
                    {step.locked && <Badge variant="outline" className="text-[10px]">payant</Badge>}
                    {state === "active" && !step.locked && (
                      <span className="text-[10px] font-mono text-muted-foreground">
                        {((Date.now() - startRef.current) / 1000).toFixed(1)} s
                      </span>
                    )}
                  </div>
                )
              })}
            </div>

            <div>
              <div className="flex justify-between text-[10px] font-mono text-muted-foreground mb-1.5">
                <span>PROGRESSION</span>
                <span>{Math.round(progress)} %</span>
              </div>
              <Progress value={progress} className="h-2" />
              <p className="text-[11px] text-center text-muted-foreground mt-3">
                vous pouvez fermer cet onglet — on vous prévient par e-mail
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

"use client"

import { Suspense, useEffect, useState } from "react"
import { useParams, useRouter, useSearchParams } from "next/navigation"
import Link from "next/link"
import { AppBar } from "@/components/layout/AppBar"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Skeleton } from "@/components/ui/skeleton"
import { Separator } from "@/components/ui/separator"
import { CheckCircle2, Circle, ArrowLeft, ArrowRight, ShieldCheck } from "lucide-react"
import { api, ApiError } from "@/lib/api"
import { SECTION_TITLES } from "@/types"
import type { Analysis } from "@/types"
import { normalizeParcours } from "@/types"

const FREE = ["1", "2", "3"]
const PAID = ["4", "5", "6", "7", "8", "9"]

export default function DebloquerPage() {
  return (
    <Suspense>
      <DebloquerContent />
    </Suspense>
  )
}

function DebloquerContent() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const searchParams = useSearchParams()

  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [loadingAnalysis, setLoadingAnalysis] = useState(true)

  const [code, setCode] = useState("")
  const [codeState, setCodeState] = useState<"idle" | "checking">("idle")
  const [error, setError] = useState<string | null>(null)

  const [paymentsEnabled, setPaymentsEnabled] = useState<boolean | null>(null)
  const [offers, setOffers] = useState<Record<string, { cents: number; description: string }> | null>(null)
  const [waiverAccepted, setWaiverAccepted] = useState(false)
  const [payState, setPayState] = useState<"idle" | "redirecting" | "verifying">(
    searchParams.get("session_id") ? "verifying" : "idle",
  )
  const canceled = searchParams.get("canceled") === "1"

  // Guard: know whether this analysis actually needs unlocking.
  useEffect(() => {
    api.get<{ analysis: Analysis }>(`/analyses/${id}`)
      .then((r) => setAnalysis(r.analysis))
      .catch(() => setAnalysis(null))
      .finally(() => setLoadingAnalysis(false))
  }, [id])

  useEffect(() => {
    api.get<{ enabled: boolean; offers: Record<string, { cents: number; description: string }> }>("/payments/config")
      .then((r) => { setPaymentsEnabled(r.enabled); setOffers(r.offers) })
      .catch(() => setPaymentsEnabled(false))
  }, [])

  // Back from Stripe with session_id → verify server-side, then watch regeneration
  useEffect(() => {
    const sessionId = searchParams.get("session_id")
    if (!sessionId) return
    api.post<{ analysis: Analysis }>("/payments/verify", { session_id: sessionId })
      .then(() => router.replace(`/analyse/en-cours/${id}`))
      .catch((e) => {
        setPayState("idle")
        setError(e instanceof ApiError ? e.message : "Vérification du paiement impossible. Contactez-nous si vous avez été débité.")
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const redeemCode = async () => {
    setError(null)
    if (!code.trim()) {
      setError("Saisissez votre code conseiller.")
      return
    }
    setCodeState("checking")
    try {
      await api.post(`/analyses/${id}/unlock`, { code })
      router.push(`/analyse/en-cours/${id}`)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erreur inattendue.")
      setCodeState("idle")
    }
  }

  const eur = (cents?: number) =>
    cents == null ? "—" : (cents % 100 === 0 ? `${cents / 100} €` : `${(cents / 100).toFixed(2)} €`)

  const startCheckout = async (tier: "paid" | "premium" = "paid") => {
    setError(null)
    if (!waiverAccepted) {
      setError("Veuillez accepter l’exécution immédiate pour continuer (droit de rétractation).")
      return
    }
    setPayState("redirecting")
    try {
      const r = await api.post<{ url: string }>("/payments/checkout", { analysis_id: id, tier })
      window.location.href = r.url
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erreur inattendue.")
      setPayState("idle")
    }
  }

  // ── Verifying (return from Stripe) ──
  if (payState === "verifying") {
    return (
      <Shell>
        <div className="mx-auto max-w-md py-24 text-center">
          <ShieldCheck className="mx-auto size-8 text-orange" />
          <p className="mt-4 font-display font-semibold text-navy">Vérification du paiement…</p>
          <p className="mt-2 text-sm text-muted-foreground">Un instant, nous confirmons votre paiement auprès de Stripe.</p>
        </div>
      </Shell>
    )
  }

  // ── Loading the analysis (guard) ──
  if (loadingAnalysis) {
    return (
      <Shell>
        <div className="mx-auto max-w-4xl space-y-4 py-6">
          <Skeleton className="h-8 w-72" />
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <Skeleton className="h-80 rounded-2xl" />
            <Skeleton className="h-80 rounded-2xl" />
          </div>
        </div>
      </Shell>
    )
  }

  const path = normalizeParcours(analysis?.inputs?._path)
  // Parcours 3 has no paid tier; parcours 1 unlocks via unlock_method.
  const alreadyComplete = path === "3" || analysis?.unlock_method != null

  // ── Nothing to unlock ──
  if (alreadyComplete) {
    return (
      <Shell>
        <div className="mx-auto max-w-md py-24 text-center">
          <CheckCircle2 className="mx-auto size-8 text-success" />
          <h1 className="mt-4 font-display text-xl font-bold text-navy">Cette analyse est déjà complète</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Aucun déblocage n’est nécessaire. Vous pouvez consulter le rapport dès maintenant.
          </p>
          <Button render={<Link href={`/analyse/${id}/rapport`} />} size="lg" className="mt-6">
            Voir le rapport <ArrowRight />
          </Button>
        </div>
      </Shell>
    )
  }

  // ── Unlock UI (Chemin A, not yet paid) ──
  return (
    <Shell>
      <div className="mx-auto max-w-4xl py-8">
        <div className="mb-2 flex items-baseline justify-between gap-3">
          <h1 className="font-display text-2xl font-bold text-navy">Débloquer le livrable complet</h1>
          <Badge variant="outline" className="font-mono text-xs">Bêta</Badge>
        </div>
        <p className="mb-6 text-sm text-muted-foreground">
          Vous avez vu les 3 premières sections. Les 6 suivantes sont la partie actionnable.
        </p>

        {error && (
          <Alert variant="destructive" className="mb-4">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        {canceled && !error && (
          <Alert className="mb-4">
            <AlertDescription>Paiement annulé. Vous pouvez réessayer quand vous voulez.</AlertDescription>
          </Alert>
        )}

        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          {/* Free card */}
          <div className="rounded-2xl bg-card p-6 ring-1 ring-foreground/10 shadow-soft">
            <p className="eyebrow text-muted-foreground">Gratuit</p>
            <p className="mt-2 font-display text-4xl font-extrabold text-navy">0 €</p>
            <p className="text-xs text-muted-foreground">Version d’essai · 1 analyse</p>
            <Separator className="my-4" />
            <ul className="space-y-2">
              {FREE.map((n) => (
                <li key={n} className="flex items-center gap-2 text-xs">
                  <CheckCircle2 className="size-3.5 shrink-0 text-orange" />§ {n} · {SECTION_TITLES[n]}
                </li>
              ))}
              {PAID.map((n) => (
                <li key={n} className="flex items-center gap-2 text-xs text-muted-foreground line-through">
                  <Circle className="size-3.5 shrink-0 opacity-30" />§ {n} · {SECTION_TITLES[n]}
                </li>
              ))}
            </ul>
          </div>

          {/* Paid card */}
          <div className="relative overflow-hidden rounded-2xl bg-navy p-6 text-white shadow-float">
            <span className="absolute inset-x-0 top-0 h-1.5 bg-brand-gradient" />
            <span className="absolute right-5 top-5"><Badge variant="peach">Recommandé</Badge></span>
            <p className="eyebrow text-peach">Complet</p>
            <div className="flex items-baseline gap-2">
              <p className="mt-2 font-display text-4xl font-extrabold">{eur(offers?.paid?.cents)}</p>
              <span className="text-sm text-white/70">une fois · sans abonnement</span>
            </div>
            <p className="text-xs text-white/70">Livrable 9 sections + CV retravaillé + export conseiller</p>
            <Separator className="my-4 bg-white/20" />
            <ul className="mb-5 space-y-2">
              {[...FREE, ...PAID].map((n) => (
                <li key={n} className="flex items-center gap-2 text-xs">
                  <CheckCircle2 className="size-3.5 shrink-0 text-peach" />§ {n} · {SECTION_TITLES[n]}
                </li>
              ))}
            </ul>

            <label className="mb-3 flex cursor-pointer items-start gap-2 text-[11px] text-white/85">
              <input
                type="checkbox"
                checked={waiverAccepted}
                onChange={(e) => setWaiverAccepted(e.target.checked)}
                className="mt-0.5 size-4 shrink-0 accent-orange"
              />
              <span>
                Je demande l’exécution immédiate du service et reconnais renoncer à mon droit de rétractation de
                14 jours (art. L221-28 du Code de la consommation). Voir les{" "}
                <Link href="/cgv" className="underline" target="_blank">CGV</Link>.
              </span>
            </label>

            <Button
              size="lg"
              className="h-11 w-full bg-white font-semibold text-orange-dark hover:bg-white/90"
              onClick={() => startCheckout("paid")}
              disabled={paymentsEnabled === false || payState === "redirecting"}
            >
              {payState === "redirecting"
                ? "Redirection vers le paiement…"
                : paymentsEnabled === false
                  ? "Paiement bientôt disponible"
                  : `Débloquer pour ${eur(offers?.paid?.cents)}`}
              {paymentsEnabled !== false && payState !== "redirecting" && <ArrowRight />}
            </Button>
            <p className="mt-2 text-center text-[10px] text-white/65">
              Paiement sécurisé par Stripe · gratuit pour les bénéficiaires Cap Emploi / France Travail (code conseiller)
            </p>
          </div>
        </div>

        {/* Premium — the modules that touch the stressful part of a search:
            the interview itself, and the questions people dread being asked. */}
        <div className="mt-6 rounded-2xl bg-card p-6 ring-1 ring-foreground/10 shadow-soft">
          <div className="flex flex-wrap items-baseline justify-between gap-3">
            <div>
              <p className="eyebrow text-orange-dark">Premium</p>
              <p className="mt-1 font-display text-lg font-bold text-navy">
                Aller jusqu&apos;à l&apos;entretien
              </p>
            </div>
            <p className="font-display text-2xl font-extrabold text-navy">
              {eur(offers?.premium?.cents)}
            </p>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            Tout le rapport complet, plus :
          </p>
          <ul className="mt-2 space-y-1.5">
            <li className="flex items-start gap-2 text-xs text-navy-700">
              <CheckCircle2 className="mt-px size-3.5 shrink-0 text-orange" />
              <span>§ 10 · Préparation à l&apos;entretien — 5 questions probables avec des réponses, et le tableau de correspondance CV / offre</span>
            </li>
            <li className="flex items-start gap-2 text-xs text-navy-700">
              <CheckCircle2 className="mt-px size-3.5 shrink-0 text-orange" />
              <span>§ 11 · Questions difficiles — trous dans le CV, RQTH, négociation : quoi dire, quand, et ce que dit la loi</span>
            </li>
          </ul>
          <Button
            variant="outline"
            size="lg"
            className="mt-4 w-full"
            onClick={() => startCheckout("premium")}
            disabled={paymentsEnabled === false || payState === "redirecting" || !waiverAccepted}
          >
            {waiverAccepted
              ? `Prendre le Premium — ${eur(offers?.premium?.cents)}`
              : "Cochez la renonciation ci-dessus pour continuer"}
          </Button>
        </div>

        {/* Counselor code */}
        <div className="mt-6 flex flex-col gap-3 rounded-2xl bg-secondary p-4 sm:flex-row sm:items-center">
          <span className="shrink-0 text-sm font-medium text-navy">Déjà un code conseiller ?</span>
          <Input
            value={code}
            onChange={(e) => setCode(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") redeemCode() }}
            placeholder="ex. A1B2C3D4"
            className="h-10 flex-1 bg-background font-mono text-sm"
          />
          <Button variant="outline" size="lg" onClick={redeemCode} disabled={codeState === "checking"}>
            {codeState === "checking" ? "Vérification…" : "Activer"}
          </Button>
        </div>

        <div className="mt-5">
          <Link href={`/analyse/${id}/rapport`} className="inline-flex items-center gap-1.5 text-sm text-muted-foreground underline-offset-2 hover:underline">
            <ArrowLeft className="size-3.5" /> Retour au rapport
          </Link>
        </div>
      </div>
    </Shell>
  )
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-background">
      <AppBar />
      <div className="px-5 sm:px-8">{children}</div>
    </div>
  )
}

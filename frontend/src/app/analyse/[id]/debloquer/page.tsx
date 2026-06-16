"use client"

import { Suspense, useEffect, useState } from "react"
import { useParams, useRouter, useSearchParams } from "next/navigation"
import Link from "next/link"
import { AppBar } from "@/components/layout/AppBar"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Separator } from "@/components/ui/separator"
import { CheckCircle2, Circle } from "lucide-react"
import { api, ApiError } from "@/lib/api"
import { SECTION_TITLES } from "@/types"
import type { Analysis } from "@/types"

const FREE  = ["1","2","3","4"]
const PAID  = ["5","6","7","8","9"]

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

  const [code, setCode] = useState("")
  const [codeState, setCodeState] = useState<"idle" | "checking">("idle")
  const [error, setError] = useState<string | null>(null)

  const [paymentsEnabled, setPaymentsEnabled] = useState<boolean | null>(null)
  const [waiverAccepted, setWaiverAccepted] = useState(false)
  const [payState, setPayState] = useState<"idle" | "redirecting" | "verifying">(
    searchParams.get("session_id") ? "verifying" : "idle"
  )
  const canceled = searchParams.get("canceled") === "1"

  useEffect(() => {
    api.get<{ enabled: boolean }>("/payments/config")
      .then(r => setPaymentsEnabled(r.enabled))
      .catch(() => setPaymentsEnabled(false))
  }, [])

  // Back from Stripe with session_id → verify server-side, then watch regeneration
  useEffect(() => {
    const sessionId = searchParams.get("session_id")
    if (!sessionId) return
    api.post<{ analysis: Analysis }>("/payments/verify", { session_id: sessionId })
      .then(() => router.replace(`/analyse/en-cours/${id}`))
      .catch(e => {
        setPayState("idle")
        setError(e instanceof ApiError ? e.message : "Vérification du paiement impossible. Contactez-nous si vous avez été débité.")
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const redeemCode = async () => {
    setError(null)
    if (!code.trim()) { setError("Saisissez votre code conseiller."); return }
    setCodeState("checking")
    try {
      await api.post(`/analyses/${id}/unlock`, { code })
      router.push(`/analyse/en-cours/${id}`)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erreur inattendue.")
      setCodeState("idle")
    }
  }

  const startCheckout = async () => {
    setError(null)
    if (!waiverAccepted) {
      setError("Veuillez accepter l'exécution immédiate pour continuer (droit de rétractation).")
      return
    }
    setPayState("redirecting")
    try {
      const r = await api.post<{ url: string }>("/payments/checkout", { analysis_id: id })
      window.location.href = r.url
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erreur inattendue.")
      setPayState("idle")
    }
  }

  if (payState === "verifying") {
    return (
      <div className="min-h-screen bg-background">
        <AppBar />
        <div className="max-w-[480px] mx-auto px-8 py-24 text-center">
          <p className="font-semibold">Vérification du paiement…</p>
          <p className="text-sm text-muted-foreground mt-2">Un instant, nous confirmons votre paiement auprès de Stripe.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      <AppBar />
      <div className="max-w-[1000px] mx-auto px-8 py-10">
        <div className="flex items-baseline justify-between mb-2">
          <h1 className="text-2xl font-bold">Débloquer le livrable complet</h1>
          <Badge variant="outline" className="font-mono text-xs">v1.3 · bêta</Badge>
        </div>
        <p className="text-sm text-muted-foreground mb-6">
          Vous avez vu les 4 premières sections. Les 5 suivantes sont la partie actionnable.
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

        <div className="grid grid-cols-2 gap-6">
          {/* Free card */}
          <div className="rounded-2xl border border-border bg-card p-6">
            <p className="font-mono text-[11px] uppercase tracking-[0.15em] text-muted-foreground">gratuit</p>
            <p className="text-4xl font-display font-extrabold text-navy mt-2">0 €</p>
            <p className="text-xs text-muted-foreground">version d&apos;essai · 1 analyse</p>
            <Separator className="my-4" />
            <ul className="space-y-2">
              {FREE.map(n => (
                <li key={n} className="flex items-center gap-2 text-xs">
                  <CheckCircle2 className="h-3.5 w-3.5 text-orange shrink-0" />
                  § {n} · {SECTION_TITLES[n]}
                </li>
              ))}
              {PAID.map(n => (
                <li key={n} className="flex items-center gap-2 text-xs text-muted-foreground line-through">
                  <Circle className="h-3.5 w-3.5 shrink-0 opacity-30" />
                  § {n} · {SECTION_TITLES[n]}
                </li>
              ))}
            </ul>
          </div>

          {/* Paid card */}
          <div className="rounded-2xl border-2 border-navy bg-navy text-white p-6 relative shadow-xl shadow-navy/20">
            <span className="absolute inset-x-0 top-0 h-1.5 bg-brand-gradient rounded-t-2xl" />
            <Badge className="absolute -top-3 right-5 bg-orange text-white border-0 text-[10px]">
              recommandé
            </Badge>
            <p className="font-mono text-[11px] uppercase tracking-[0.15em] text-peach">complet</p>
            <div className="flex items-baseline gap-2">
              <p className="text-4xl font-display font-extrabold mt-2">9 €</p>
              <span className="text-sm text-white/70">une fois · sans abonnement</span>
            </div>
            <p className="text-xs text-white/70">livrable 9 sections + CV retravaillé + export conseiller</p>
            <Separator className="my-4 bg-white/20" />
            <ul className="space-y-2 mb-5">
              {[...FREE,...PAID].map(n => (
                <li key={n} className="flex items-center gap-2 text-xs">
                  <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-peach" />
                  § {n} · {SECTION_TITLES[n]}
                </li>
              ))}
            </ul>

            <label className="flex items-start gap-2 text-[11px] text-white/85 mb-3 cursor-pointer">
              <input
                type="checkbox"
                checked={waiverAccepted}
                onChange={e => setWaiverAccepted(e.target.checked)}
                className="mt-0.5 shrink-0 accent-orange"
              />
              <span>
                Je demande l&apos;exécution immédiate du service et reconnais renoncer à mon droit de
                rétractation de 14 jours (art. L221-28 du Code de la consommation). Voir les{" "}
                <Link href="/cgv" className="underline" target="_blank">CGV</Link>.
              </span>
            </label>

            <Button
              className="w-full bg-orange text-white hover:bg-orange-dark font-semibold"
              onClick={startCheckout}
              disabled={paymentsEnabled === false || payState === "redirecting"}
            >
              {payState === "redirecting"
                ? "Redirection vers le paiement…"
                : paymentsEnabled === false
                  ? "paiement bientôt disponible"
                  : "débloquer pour 9 € →"}
            </Button>
            <p className="text-[10px] text-white/65 text-center mt-2">
              paiement sécurisé par Stripe · code conseiller — gratuit pour les bénéficiaires Cap Emploi / France Travail
            </p>
          </div>
        </div>

        {/* Counselor code input */}
        <div className="mt-6 rounded-lg border border-border bg-secondary p-4 flex items-center gap-4">
          <span className="font-medium text-sm shrink-0">déjà un code conseiller ?</span>
          <Input
            value={code}
            onChange={e => setCode(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter") redeemCode() }}
            placeholder="ex. A1B2C3D4"
            className="font-mono text-sm flex-1 bg-background"
          />
          <Button variant="outline" size="sm" onClick={redeemCode} disabled={codeState === "checking"}>
            {codeState === "checking" ? "vérification…" : "activer"}
          </Button>
        </div>

        <div className="mt-4">
          <Link href={`/analyse/${id}/rapport`} className="text-xs text-muted-foreground underline underline-offset-2">
            ← Retour au rapport
          </Link>
        </div>
      </div>
    </div>
  )
}

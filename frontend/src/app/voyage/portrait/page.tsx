"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { ArrowLeft, Printer } from "lucide-react"

import { AppBar } from "@/components/layout/AppBar"
import { Logo } from "@/components/brand/Logo"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { api, ApiError } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { errorStatus, getPortrait } from "@/lib/voyage"
import { PORTRAIT_SECTIONS, type CandidatePortrait } from "@/types/voyage"

/** What to say for each portrait_status the 409 can carry, plus the no-voyage
 *  404's own message (it carries no `status`, so it never matches this map —
 *  see the fallback below). Chrome, so vouvoiement — the portrait's own six
 *  sections stay tutoiement. Rulings (Tasks 7-10 overrides) replace the
 *  plan's draft/error copy; "none" is unchanged. */
const PENDING: Record<string, string> = {
  none: "Votre portrait n'a pas encore été rédigé. Il arrive une fois les six sessions terminées.",
  generating: "Votre portrait est en cours de rédaction.",
  draft: "Votre portrait est rédigé et attend d'être relu avec votre conseiller. Le lien à lui transmettre se trouve sur la page du voyage.",
  error: "La rédaction de votre portrait n'a pas abouti. Votre conseiller peut la relancer depuis le lien disponible sur la page du voyage.",
}

type Profile = { prenom?: string | null }

export default function VoyagePortraitPage() {
  const router = useRouter()
  const { user, loading: authLoading } = useAuth()

  const [portrait, setPortrait] = useState<CandidatePortrait | null>(null)
  const [pending, setPending] = useState<string | null>(null)
  const [prenom, setPrenom] = useState<string>("")
  const [loaded, setLoaded] = useState(false)
  // A load failure that is neither the 409 (portrait not validated yet) nor
  // the 404 (no voyage at all) — a real error, offering a retry instead of
  // the "wait for your counselor" copy above (house pattern:
  // frontend/src/app/voyage/page.tsx's loadError).
  const [loadError, setLoadError] = useState<string | null>(null)
  // Guards a double click on "Réessayer", same as the hub/player.
  const [reloading, setReloading] = useState(false)

  useEffect(() => {
    if (!authLoading && !user) router.replace("/connexion?redirect=/voyage/portrait")
  }, [authLoading, user, router])

  // The loader: profile (for the header's first name) + the portrait. Every
  // setState below happens inside a .then/.catch/.finally callback, never
  // synchronously at the top of the effect body (react-hooks/set-state-in-effect),
  // so the mount effect can call this directly. A 409 or 404 on the portrait
  // call is not an error — it is one of the PENDING states — but any other
  // rejection (500, a network failure, …) is, and gets loadError + Réessayer.
  const load = useCallback(() => {
    return Promise.all([
      api.get<{ profile: Profile | null }>("/profile", { skipRedirect: true })
        .then((r) => r.profile?.prenom ?? "")
        .catch(() => ""),
      getPortrait()
        .then((p) => ({ portrait: p, pending: null as string | null }))
        .catch((e: unknown) => {
          if (e instanceof ApiError && (e.status === 409 || e.status === 404)) {
            const status = errorStatus(e)
            return {
              portrait: null,
              pending: (status && PENDING[status]) ?? e.message,
            }
          }
          throw e
        }),
    ])
      .then(([p, result]) => {
        setLoadError(null)
        setPrenom(p)
        setPortrait(result.portrait)
        setPending(result.pending)
      })
      .catch((e) => {
        setLoadError(e instanceof ApiError ? e.message : "Erreur inattendue.")
      })
      .finally(() => {
        setLoaded(true)
      })
  }, [])

  // R15: the loader waits for auth — it never fires while a token is still
  // being checked or has come back empty (that case is the redirect above).
  useEffect(() => {
    if (authLoading || !user) return
    load()
  }, [authLoading, user, load])

  // Wraps load() for the loadError "Réessayer" button — disables it and
  // swaps its label while a retry is in flight, and a second click cannot
  // start a parallel load (house pattern: frontend/src/app/voyage/page.tsx).
  const retryLoad = useCallback(() => {
    if (reloading) return
    setReloading(true)
    load().finally(() => setReloading(false))
  }, [load, reloading])

  if (authLoading || !user || !loaded) {
    return (
      <div className="min-h-screen bg-secondary">
        <AppBar />
        <div className="px-4 py-8">
          <Skeleton className="mx-auto h-[600px] w-[620px] max-w-full rounded-xl" />
        </div>
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="min-h-screen bg-secondary">
        <AppBar />
        <div className="mx-auto max-w-2xl px-4 py-16 text-center">
          <Alert variant="destructive" className="mb-4 text-left">
            <AlertDescription>{loadError}</AlertDescription>
          </Alert>
          <Button size="lg" onClick={retryLoad} disabled={reloading}>
            {reloading ? "Chargement…" : "Réessayer"}
          </Button>
        </div>
      </div>
    )
  }

  if (!portrait) {
    return (
      <div className="min-h-screen bg-secondary">
        <AppBar />
        <div className="mx-auto max-w-2xl px-4 py-16 text-center">
          <p className="font-display text-lg font-bold text-navy">Votre portrait</p>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{pending}</p>
          <Button render={<Link href="/voyage" />} size="lg" className="mt-5">
            Retour au voyage
          </Button>
        </div>
      </div>
    )
  }

  const validated = portrait.validated_at
    ? new Date(portrait.validated_at).toLocaleDateString("fr-FR", {
        day: "2-digit", month: "long", year: "numeric",
      })
    : ""

  return (
    <div className="min-h-screen bg-secondary">
      <AppBar />

      {/* R20: AppBar is h-20 (frontend/src/components/layout/AppBar.tsx:26),
          so sticky top-20 keeps this bar flush beneath it. The rapport
          page's top-16 is the odd one out — not to be copied here. */}
      <div className="no-print sticky top-20 z-40 flex flex-wrap items-center justify-center gap-2 border-b border-border bg-secondary/95 py-3 backdrop-blur-sm">
        <Button
          render={<Link href="/voyage" />}
          variant="outline"
          size="sm"
        >
          <ArrowLeft className="size-3.5" /> Le voyage
        </Button>
        <Button variant="outline" size="sm" onClick={() => setTimeout(() => window.print(), 50)}>
          <Printer className="size-3.5" /> PDF
        </Button>
      </div>

      <div className="px-4 py-8">
        <div className="report-shell">
          <div className="voyage-rule" />

          <div className="bg-navy px-8 pb-6 pt-6 text-white">
            <Logo tone="light" className="text-base" />
            <h1 className="mt-3 font-display text-2xl font-extrabold leading-tight text-white">
              {prenom || "Votre portrait"}
            </h1>
            <p className="mt-1 text-sm italic text-peach">
              Portrait du voyage{validated ? ` · validé le ${validated}` : ""}
            </p>
          </div>

          <div className="px-8 py-7">
            {PORTRAIT_SECTIONS.map(({ key, title }) => {
              const body = portrait.sections[key]
              if (!body) return null
              return (
                <section key={key} className="print-break mb-7 last:mb-0">
                  <h2 className="mb-2 font-display text-sm font-semibold uppercase tracking-wide text-navy">
                    {title}
                  </h2>
                  <p
                    className={
                      key === "accroche"
                        ? "whitespace-pre-line font-display text-lg italic leading-relaxed text-navy"
                        : "whitespace-pre-line text-sm leading-relaxed text-navy-700"
                    }
                  >
                    {body}
                  </p>
                </section>
              )
            })}

            <div className="mt-8 flex items-center justify-between border-t border-border pt-4">
              <span className="font-mono text-[10px] text-muted-foreground">neoori · confidentiel</span>
              <span className="font-mono text-[10px] text-muted-foreground">{validated}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

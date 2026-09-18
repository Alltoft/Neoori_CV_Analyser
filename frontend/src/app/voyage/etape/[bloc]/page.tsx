"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"
import { ArrowLeft, ArrowRight, ShieldCheck } from "lucide-react"

import { AppBar } from "@/components/layout/AppBar"
import { ConditionsMatrix } from "@/components/profil/ConditionsMatrix"
import { LiveSynthesis } from "@/components/profil/LiveSynthesis"
import { ProfileStepFields } from "@/components/voyage/ProfileStepFields"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Skeleton } from "@/components/ui/skeleton"
import { api, ApiError } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { PROFILE_STEPS, isStepKey, stepIsComplete } from "@/lib/profile-steps"
import type { ConditionsValue } from "@/types/conditions"

/**
 * One block of the Profil de base, asked inside the voyage.
 *
 * `parcours` sits between sessions 1 and 2, `conditions` between 4 and 5, and
 * `session_lock` refuses the next session until the block is answered — so
 * this page is the remedy a locked card points at, not a detour someone has
 * to discover. The hub inlines `entree` on its own consent gate; it is served
 * here too so a link to any block resolves.
 *
 * Nothing here restitutes: the steps ask, and the person reads what came of it
 * in their phrase and their portrait. No score, no trait name, no framework.
 */

/** The ordinary profile fields this page may write. Everything else on the
 *  profile belongs to another step or to /profil, and a PUT that carried it
 *  would clear it — the API replaces the fields it is given. */
type ProfilePayload = Record<string, string | boolean | ConditionsValue>

export default function ProfileStepPage() {
  const router = useRouter()
  const params = useParams<{ bloc: string }>()
  const { user, loading: authLoading } = useAuth()

  const bloc = params?.bloc
  const step = isStepKey(bloc) ? PROFILE_STEPS[bloc] : null

  const [values, setValues] = useState<Record<string, string>>({})
  const [conditions, setConditions] = useState<ConditionsValue>({})
  const [oeth, setOeth] = useState(false)
  // Bloc 5 and the OETH flag are GDPR Art. 9 data; the CGV tick at signup does
  // not cover them. The server refuses to store either without this.
  const [consentSensitive, setConsentSensitive] = useState(false)
  const [consentSensitiveOnRecord, setConsentSensitiveOnRecord] = useState(false)
  // Accounts created before signup seeded a profile have no consent record at
  // all, so the first step they reach has to collect the ordinary one too.
  const [needsConsent, setNeedsConsent] = useState(false)
  const [consent, setConsent] = useState(false)

  const [loaded, setLoaded] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // The proxy gates /voyage on cookie *presence*, which misses an expired
  // token — same guard as the hub and /profil.
  useEffect(() => {
    if (!authLoading && !user) router.replace(`/connexion?redirect=/voyage/etape/${bloc}`)
  }, [authLoading, user, router, bloc])

  const load = useCallback(() => {
    const wantsConditions = step?.kind === "conditions"
    return Promise.all([
      api.get<{ profile: Record<string, string | null> | null }>("/profile", { skipRedirect: true }),
      wantsConditions
        ? api.get<{ conditions: ConditionsValue; oeth: boolean }>(
            "/profile/conditions", { skipRedirect: true },
          )
        : Promise.resolve(null),
    ])
      .then(([{ profile }, sensitive]) => {
        setNeedsConsent(!profile?.consent_at)
        setConsentSensitiveOnRecord(Boolean(profile?.consent_sensitive_at))
        setValues(Object.fromEntries(
          (step?.fields ?? []).map((field) => [field.name, profile?.[field.name] ?? ""]),
        ))
        if (sensitive) {
          setConditions(sensitive.conditions ?? {})
          setOeth(Boolean(sensitive.oeth))
        }
        setError(null)
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Erreur inattendue."))
      .finally(() => setLoaded(true))
  }, [step])

  useEffect(() => {
    if (authLoading || !user || !step) return
    load()
  }, [authLoading, user, step, load])

  if (!step) {
    return (
      <div className="min-h-dvh bg-background">
        <AppBar />
        <div className="mx-auto max-w-2xl px-5 py-12 sm:px-8">
          <Alert variant="destructive">
            <AlertDescription>Cette étape n&apos;existe pas.</AlertDescription>
          </Alert>
          <Button render={<Link href="/voyage" />} variant="outline" size="lg" className="mt-5">
            <ArrowLeft className="size-4" /> Retour au voyage
          </Button>
        </div>
      </div>
    )
  }

  const isConditions = step.kind === "conditions"
  // The conditions step is answerable by leaving everything empty — bloc 5 is
  // optional for everyone — so what gates it is the consent, never an answer.
  const ready = isConditions
    ? consentSensitiveOnRecord || consentSensitive
    : stepIsComplete(step, values)
  const blocked = needsConsent && !consent

  const save = async () => {
    setSaving(true)
    setError(null)
    const payload: ProfilePayload = {}

    for (const field of step.fields) {
      payload[field.name] = (values[field.name] ?? "").trim()
    }

    if (isConditions) {
      // Sent together or not at all. Omitting on the value of `oeth` would be
      // a reaction to the flag; omitting on the consent is symmetric, and the
      // button is disabled until that consent exists anyway.
      payload.conditions = conditions
      payload.oeth = oeth
      if (consentSensitive) payload.consent_sensitive = true
    }

    // Only for a profile that has none: re-sending it would restamp a consent
    // the person gave once, at signup.
    if (needsConsent) payload.consent = true

    try {
      await api.put("/profile", payload)
      router.push(step.done)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erreur lors de l'enregistrement.")
      setSaving(false)
    }
  }

  return (
    <div className="min-h-dvh bg-background">
      <AppBar />

      <div className="mx-auto max-w-2xl px-5 py-10 sm:px-8 sm:py-12">
        <Link href="/voyage" className="link-underline inline-flex items-center gap-1.5 text-xs text-muted-foreground">
          <ArrowLeft className="size-3.5" aria-hidden /> Le voyage
        </Link>

        <h1 className="mt-4 font-display text-2xl font-bold text-navy">{step.title}</h1>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{step.intro}</p>

        {error && (
          <Alert variant="destructive" className="mt-5">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {!loaded ? (
          <div className="mt-7 space-y-4">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </div>
        ) : (
          <div className="mt-7 space-y-6">
            {isConditions ? (
              <>
                <ConditionsMatrix value={conditions} onChange={setConditions} />
                <LiveSynthesis value={conditions} />

                {/* The OETH box must trigger nothing visible: no new field, no
                    re-layout, no extra request. The effect appears only in the
                    generated report. Nothing here may react to it. */}
                <label className="flex cursor-pointer items-start gap-3 rounded-lg bg-secondary/60 p-3">
                  <Checkbox className="mt-0.5" checked={oeth} onCheckedChange={(v) => setOeth(v === true)} />
                  <span className="text-xs leading-relaxed text-navy-700">
                    Je suis bénéficiaire de l&apos;obligation d&apos;emploi des travailleurs
                    handicapés (OETH).
                    <span className="mt-1 block text-muted-foreground">
                      L&apos;OETH est un statut administratif qui ouvre des droits —
                      accompagnement Cap Emploi, financement d&apos;aménagements par
                      l&apos;Agefiph. Cette information est stockée séparément et chiffrée.
                      Elle n&apos;apparaît jamais dans votre rapport ni dans les documents que
                      vous partagez.
                    </span>
                  </span>
                </label>

                {!consentSensitiveOnRecord && (
                  <label className="flex cursor-pointer items-start gap-3 rounded-lg bg-secondary/60 p-3 has-[:checked]:bg-peach-soft/60">
                    <Checkbox
                      className="mt-0.5"
                      checked={consentSensitive}
                      onCheckedChange={(v) => setConsentSensitive(v === true)}
                    />
                    <span className="text-xs leading-relaxed text-navy-700">
                      J&apos;accepte que ces réponses sur mes conditions de travail soient
                      conservées, chiffrées et séparées du reste de mon profil, pour rendre
                      mon rapport plus précis.
                      <span className="mt-1 block text-muted-foreground">
                        Vous pouvez les modifier ou les supprimer à tout moment depuis votre
                        profil.
                      </span>
                    </span>
                  </label>
                )}
              </>
            ) : (
              <ProfileStepFields step={step} values={values} disabled={saving}
                onChange={(name, value) => setValues((v) => ({ ...v, [name]: value }))} />
            )}

            {needsConsent && (
              <label className="flex cursor-pointer items-start gap-3 rounded-lg bg-secondary/60 p-3 has-[:checked]:bg-peach-soft/60">
                <Checkbox className="mt-0.5" checked={consent} onCheckedChange={(v) => setConsent(v === true)} />
                <span className="text-xs leading-relaxed text-navy-700">
                  J&apos;accepte que mes données soient traitées pour produire mon analyse et
                  mon accompagnement. Je peux les consulter, les corriger et les supprimer à
                  tout moment depuis mon espace.
                </span>
              </label>
            )}

            <div className="flex flex-col items-start justify-between gap-3 rounded-2xl bg-card p-5 ring-1 ring-foreground/10 sm:flex-row sm:items-center">
              <p className="flex items-center gap-2 text-xs text-muted-foreground">
                <ShieldCheck className="size-3.5 shrink-0 text-success" aria-hidden />
                Données chiffrées, supprimables à tout moment.
              </p>
              <Button size="lg" disabled={!ready || blocked || saving} onClick={save}>
                {saving ? "Enregistrement…" : "Continuer"}
                <ArrowRight className="size-4" />
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

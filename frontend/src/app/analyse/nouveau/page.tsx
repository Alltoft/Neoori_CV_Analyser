"use client"

import { useState, useCallback, useEffect, Suspense } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import Link from "next/link"
import { AppLink } from "@/lib/site-context"
import { useForm, Controller } from "react-hook-form"
import { useAuth } from "@/lib/auth"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { AppBar } from "@/components/layout/AppBar"
import { DOORS_PANEL_ID, DoorsPanel, type DoorId } from "@/components/analyse/DoorsPanel"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { SectionCard } from "@/components/ui/section-card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { api, ApiError } from "@/lib/api"
import { held } from "@/lib/held"
import { cn } from "@/lib/utils"
import type { Analysis } from "@/types"
import { UploadCloud, FileText, ArrowRight, Check, ShieldCheck } from "lucide-react"

// Parcours 1 asks for two things: a CV and a target. Identity, age, location,
// situation and constraints live in the Profil de base and are folded in
// server-side by _merge_profile — "une information, une seule fois"
// (Parcours doc §1).

// Parcours 1 has two chemins (Parcours doc §4), and they are not the same
// question as "uploaded or typed" — the doc's chemin A is literally "coller
// l'offre d'emploi exacte", so a pasted ad is still chemin A. What separates
// them is whether the text IS the employer's ad or the person's own
// description of a target, and only they can say which.
const CHEMINS = [
  {
    value: "A" as const,
    label: "J'ai l'offre",
    hint: "Le rapport compare votre CV à l'offre, exigence par exigence.",
  },
  {
    value: "B" as const,
    label: "Je décris ma cible",
    hint: "Le rapport s'ouvre en disant qu'il part de votre description.",
  },
]

// Mirrors CIBLE_MIN in backend/app/routes/analyses.py.
const CIBLE_MIN = { A: 50, B: 20 } as const

const schema = z
  .object({
    cv_text: z.string().min(200, "CV trop court (200 caractères minimum)."),
    chemin: z.enum(["A", "B"]),
    cible_visee: z.string(),
  })
  .superRefine((v, ctx) => {
    const min = CIBLE_MIN[v.chemin]
    if (v.cible_visee.trim().length < min) {
      ctx.addIssue({
        code: "custom",
        path: ["cible_visee"],
        message: `Cible trop courte (${min} caractères minimum).`,
      })
    }
  })
type Fields = z.infer<typeof schema>

/** Form shape → stored inputs. `_chemin` follows the `_path` / `_tier`
 *  discriminator convention rather than the form's own field name. */
function toInputs({ chemin, ...rest }: Fields) {
  return { ...rest, _chemin: chemin }
}

/** Where the sign-in link under « Enregistrer le brouillon » brings the person
 *  back after a lapsed session (ruling R14): the form, refilled from the draft
 *  this browser holds, with no door open — they only wanted their form back. */
const DRAFT_RETURN = "/analyse/nouveau?reprendre=brouillon"

export default function NouvelleAnalysePage() {
  return (
    <Suspense>
      <NouvelleAnalyseForm />
    </Suspense>
  )
}

function NouvelleAnalyseForm() {
  const router = useRouter()
  const { user, loading: authLoading } = useAuth()
  // The form opens to everyone (four-doors spec): it waits only for auth to
  // resolve, so the doors know who is there.
  const ready = !authLoading
  const searchParams = useSearchParams()
  const [draftId, setDraftId] = useState<string | null>(searchParams.get("draft"))
  const [draftState, setDraftState] = useState<"idle" | "saving" | "saved" | "error" | "held">("idle")
  const [uploadState, setUploadState] = useState<"idle" | "uploading" | "done" | "error">("idle")
  const [uploadedFilename, setUploadedFilename] = useState<string>("")
  const [projectUploadState, setProjectUploadState] = useState<"idle" | "uploading" | "done" | "error">("idle")
  const [projectUploadedFilename, setProjectUploadedFilename] = useState<string>("")
  const [isDragging, setIsDragging] = useState(false)
  const [isProjectDragging, setIsProjectDragging] = useState(false)
  const [panelOpen, setPanelOpen] = useState(false)
  const [initialDoor, setInitialDoor] = useState<DoorId | null>(null)
  const [resumeNotice, setResumeNotice] = useState<string | null>(null)

  const { register, handleSubmit, control, setValue, watch, reset, formState: { errors } } = useForm<Fields>({
    resolver: zodResolver(schema),
    defaultValues: { chemin: "A" },
  })

  const chemin = watch("chemin")

  // Resume a saved draft (?draft=<id>)
  useEffect(() => {
    if (!draftId) return
    api.get<{ analysis: Analysis }>(`/analyses/${draftId}`, { skipRedirect: true })
      .then(({ analysis }) => {
        if (analysis.status !== "draft" || !analysis.inputs) return
        const i = analysis.inputs
        // Drafts saved before the profile migration carry the old fields;
        // they are simply not restored, and the profile supplies them instead.
        reset({
          cv_text: i.cv_text ?? "",
          cible_visee: i.cible_visee ?? "",
          chemin: i._chemin === "B" ? "B" : "A",
        })
      })
      .catch(() => { /* draft gone — start blank */ })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Back from a sign-in round trip (?reprendre=compte|promo): refill the form
  // from the held draft and reopen the panel at that door (four-doors spec,
  // decision 34). The person confirms; nothing starts on its own.
  // ?reprendre=brouillon is the way back from the lapsed-session link under
  // « Enregistrer le brouillon » (ruling R14): same restore, but no door.
  // Once it has run, whatever the outcome, ?reprendre= is dropped from the URL:
  // it is a one-shot instruction, and left in the history entry it would replay
  // on Back, after a submit promoted the draft, as a false « formulaire resté
  // sur l’appareil ».
  useEffect(() => {
    const porte = searchParams.get("reprendre")
    if (!porte || authLoading) return
    const door: DoorId | null = porte === "brouillon" ? null : porte === "promo" ? "promo" : "account"
    // A run can be cleaned up before it settles (the page is left; Strict Mode
    // runs effects twice in dev): only the live run touches the form or the URL.
    let live = true
    const restore = (a: Analysis, owned: boolean) => {
      const i = a.inputs ?? {}
      reset({ cv_text: i.cv_text ?? "", cible_visee: i.cible_visee ?? "", chemin: i._chemin === "B" ? "B" : "A" })
      if (owned) setDraftId(a.id)
      if (door) {
        setInitialDoor(door)
        setPanelOpen(true)
      }
    }
    const resume = async () => {
      try {
        if (!user) {
          const { analysis } = await held.get()
          if (live) restore(analysis, false)
          return
        }
        let draft: Analysis | undefined
        try {
          draft = (await held.claim()).analysis
        } catch (e) {
          // Only « nothing held » (404) falls back. Any other failure is shown
          // as it is: guessing around it would restore the wrong thing.
          if (!(e instanceof ApiError && e.status === 404)) throw e
          // Verified on another device: signup attached the draft to this
          // account at verify-email, so it is the account's latest draft.
          const { analyses } = await api.get<{ analyses: Analysis[] }>("/analyses/", { skipRedirect: true })
          draft = analyses.find((a) => a.status === "draft")
          if (!draft) {
            if (live) setResumeNotice("Votre formulaire est resté sur l’appareil où vous l’avez rempli : connectez-vous depuis celui-ci pour le retrouver.")
            return
          }
        }
        if (live) restore(draft, true)
      } catch (e) {
        if (live) setResumeNotice(e instanceof ApiError ? e.message : "Erreur inattendue.")
      } finally {
        if (live) router.replace("/analyse/nouveau", { scroll: false })
      }
    }
    resume()
    return () => { live = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authLoading])

  const handleFile = useCallback(async (file: File) => {
    if (file.type !== "application/pdf") { setUploadState("error"); return }
    setUploadState("uploading")
    const fd = new FormData()
    fd.append("file", file)
    try {
      const res = await api.upload<{ cv_text: string }>("/upload/cv", fd)
      setValue("cv_text", res.cv_text, { shouldValidate: true })
      setUploadedFilename(file.name)
      setUploadState("done")
    } catch {
      setUploadState("error")
    }
  }, [setValue])

  const handleProjectFile = useCallback(async (file: File) => {
    if (file.type !== "application/pdf") { setProjectUploadState("error"); return }
    setProjectUploadState("uploading")
    const fd = new FormData()
    fd.append("file", file)
    try {
      const res = await api.upload<{ projet_text: string }>("/upload/projet", fd)
      setValue("cible_visee", res.projet_text, { shouldValidate: true })
      // A deposited document is the employer's, not a description of a target.
      setValue("chemin", "A", { shouldValidate: true })
      setProjectUploadedFilename(file.name)
      setProjectUploadState("done")
    } catch {
      setProjectUploadState("error")
    }
  }, [setValue])

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setIsDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }, [handleFile])

  const onProjectDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setIsProjectDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleProjectFile(file)
  }, [handleProjectFile])

  // Validation passed: the doors decide what happens next (four-doors spec).
  const onSubmit = () => setPanelOpen(true)

  // The button is shown to signed-in visitors only, but a session can lapse
  // under an open page: the backend then keeps the draft in this browser and
  // says so with "held" (ruling R13).
  const saveDraft = async () => {
    setDraftState("saving")
    try {
      const res = await api.post<{ analysis: Analysis; held?: boolean }>(
        "/analyses/draft",
        { inputs: toInputs(watch()), draft_id: draftId ?? undefined },
        { skipRedirect: true },
      )
      if (res.held) {
        // Not the account's draft: no draftId to carry, and no « Brouillon enregistré ».
        setDraftState("held")
        return
      }
      setDraftId(res.analysis.id)
      setDraftState("saved")
      setTimeout(() => setDraftState((s) => (s === "saved" ? "idle" : s)), 4000)
    } catch {
      setDraftState("error")
    }
  }

  const dropZone = (kind: "cv" | "projet") => {
    const state = kind === "cv" ? uploadState : projectUploadState
    const filename = kind === "cv" ? uploadedFilename : projectUploadedFilename
    const dragging = kind === "cv" ? isDragging : isProjectDragging
    const inputId = `${kind}-file-input`
    return (
      <div
        onDrop={kind === "cv" ? onDrop : onProjectDrop}
        onDragOver={(e) => { e.preventDefault(); kind === "cv" ? setIsDragging(true) : setIsProjectDragging(true) }}
        onDragLeave={() => (kind === "cv" ? setIsDragging(false) : setIsProjectDragging(false))}
        onClick={() => document.getElementById(inputId)?.click()}
        className={cn(
          "flex h-32 cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed transition-colors",
          dragging ? "border-orange bg-orange/5" : "border-border bg-secondary hover:border-orange/50",
          state === "done" && "border-success/40 bg-success/5",
        )}
      >
        <input
          id={inputId}
          type="file"
          accept="application/pdf"
          className="hidden"
          onChange={(e) => e.target.files?.[0] && (kind === "cv" ? handleFile : handleProjectFile)(e.target.files[0])}
        />
        {state === "done" ? (
          <>
            <FileText className="size-5 text-success" />
            <span className="px-3 text-center text-xs font-medium text-success">{filename}</span>
          </>
        ) : state === "uploading" ? (
          <span className="text-xs text-muted-foreground">Extraction en cours…</span>
        ) : (
          <>
            <UploadCloud className="size-5 text-muted-foreground" />
            <span className="text-xs font-medium text-navy">Déposer un PDF</span>
            <span className="text-[10px] text-muted-foreground">glissez ici, ou cliquez</span>
            <Badge variant="outline" className="text-[10px]">PDF · 10 Mo max</Badge>
          </>
        )}
        {state === "error" && <span className="text-[10px] text-destructive">Fichier PDF uniquement.</span>}
      </div>
    )
  }

  // No form until auth has resolved, so the doors know who is there (signed in
  // or not) and the draft/panel choices below are right on the first paint. A
  // draft that loads meanwhile is reset() into the form before it mounts,
  // and the fields pick it up when they register.
  if (!ready) {
    return (
      <div className="min-h-screen bg-background">
        <AppBar />
        <div className="bg-orange h-1.5 w-full" role="presentation" aria-hidden />
        <div className="mx-auto max-w-3xl px-5 py-10 sm:px-8">
          <Skeleton className="h-8 w-56" />
          <div className="mt-8 space-y-4">
            {[0, 1].map((i) => <Skeleton key={i} className="h-48 rounded-2xl" />)}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      <AppBar />
      {/* The analysis' accent: orange, like the report rule. */}
      <div className="bg-orange h-1.5 w-full" role="presentation" aria-hidden />
      <div className="mx-auto max-w-3xl px-5 py-10 sm:px-8">
        <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
          <h1 className="font-display text-2xl font-bold text-navy">Nouvelle analyse</h1>
          <Badge variant="outline" className="font-mono text-xs">~2 min</Badge>
        </div>
        <p className="mb-8 text-sm text-muted-foreground">
          {user ? "Votre CV et la cible que vous visez. Le reste vient de votre profil." : "Votre CV et la cible que vous visez."}
        </p>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {resumeNotice && <Alert><AlertDescription>{resumeNotice}</AlertDescription></Alert>}

          <SectionCard n={1} title="Votre CV">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-[1.2fr_1fr]">
              {dropZone("cv")}
              <div className="flex flex-col gap-1.5">
                <span className="text-center text-[10px] text-muted-foreground">— ou copier-coller le texte —</span>
                <Textarea {...register("cv_text")} placeholder="Collez le texte de votre CV ici…" className="min-h-[104px] flex-1 resize-none bg-background text-sm" />
              </div>
            </div>
            {errors.cv_text && <p className="mt-2 text-xs text-destructive">{errors.cv_text.message}</p>}
          </SectionCard>

          <SectionCard n={2} title="Votre projet" hint="Offre d’emploi, fiche métier ou programme de formation.">
            <Controller
              name="chemin"
              control={control}
              render={({ field }) => (
                <div role="radiogroup" aria-label="Type de cible" className="mb-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {CHEMINS.map((c) => (
                    <button
                      key={c.value}
                      type="button"
                      role="radio"
                      aria-checked={field.value === c.value}
                      onClick={() => field.onChange(c.value)}
                      className={cn(
                        "rounded-xl border px-3 py-2.5 text-left transition-colors",
                        field.value === c.value
                          ? "border-navy bg-navy text-white"
                          : "border-border bg-background text-navy hover:border-orange/50",
                      )}
                    >
                      <span className="block text-xs font-semibold">{c.label}</span>
                      <span className={cn("mt-0.5 block text-[10px] leading-snug", field.value === c.value ? "text-white/75" : "text-muted-foreground")}>
                        {c.hint}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            />
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-[1.2fr_1fr]">
              {dropZone("projet")}
              <div className="flex flex-col gap-1.5">
                <span className="text-center text-[10px] text-muted-foreground">
                  {chemin === "B" ? "— ou décrire librement —" : "— ou coller le texte de l’offre —"}
                </span>
                <Textarea
                  {...register("cible_visee")}
                  placeholder={chemin === "B"
                    ? "Le poste ou le secteur que vous visez…"
                    : "Collez ici le texte de l’offre d’emploi…"}
                  className="min-h-[104px] flex-1 resize-none bg-background text-sm"
                />
              </div>
            </div>
            {errors.cible_visee && <p className="mt-2 text-xs text-destructive">{errors.cible_visee.message}</p>}
          </SectionCard>

          {user && (
            <p className="rounded-2xl bg-card p-4 text-xs text-muted-foreground ring-1 ring-foreground/10">
              Le reste de l’analyse s’appuie sur ce que vous avez déjà donné — prénom,
              localisation, situation, contraintes. Ces questions sont posées à
              l’inscription et au fil du{" "}
              <AppLink href="/voyage" className="link-underline text-navy">voyage</AppLink> ; vous
              pouvez les relire dans{" "}
              <Link href="/profil" className="link-underline text-navy">mes informations</Link>.
            </p>
          )}

          {/* Footer */}
          <div className="flex flex-col gap-4 border-t border-border pt-5 sm:flex-row sm:items-center sm:justify-between">
            {user && (
              <div className="flex flex-col gap-1">
                <Button type="button" variant="outline" onClick={saveDraft} disabled={draftState === "saving"} className="self-start">
                  {draftState === "saving" ? "Enregistrement…" : draftState === "saved" ? <><Check className="size-4 text-success" /> Brouillon enregistré</> : "Enregistrer le brouillon"}
                </Button>
                {/* Information, not a failure: the draft is safe in this browser. */}
                {draftState === "held" && (
                  <span className="text-xs text-muted-foreground">
                    Votre session a expiré : ce brouillon est gardé dans ce navigateur.{" "}
                    <Link href={`/connexion?redirect=${encodeURIComponent(DRAFT_RETURN)}`} className="text-navy underline underline-offset-2">Connectez-vous</Link> pour l’enregistrer dans votre espace.
                  </span>
                )}
                {draftState === "error" && <span className="text-xs text-destructive">Échec de l’enregistrement. Réessayez.</span>}
              </div>
            )}

            {/* sm:ml-auto keeps it on the right when the draft button is not there (signed out). */}
            <Button type="submit" size="xl" className="sm:ml-auto" aria-expanded={panelOpen} aria-controls={DOORS_PANEL_ID}>
              Générer mon analyse <ArrowRight />
            </Button>
          </div>

          <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <ShieldCheck className="size-3.5 text-success" />
            Données chiffrées, supprimables à tout moment.
          </p>
        </form>

        {panelOpen && (
          <div className="mt-6">
            <DoorsPanel
              inputs={() => toInputs(watch())}
              draftId={draftId}
              initialDoor={initialDoor}
              onClose={() => setPanelOpen(false)}
            />
          </div>
        )}
      </div>
    </div>
  )
}

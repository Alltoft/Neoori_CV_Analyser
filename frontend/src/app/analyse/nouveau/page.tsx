"use client"

import { useState, useCallback, useEffect, Suspense } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import Link from "next/link"
import { useForm, Controller } from "react-hook-form"
import { useAuth } from "@/lib/auth"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { AppBar } from "@/components/layout/AppBar"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { api, ApiError } from "@/lib/api"
import { cn } from "@/lib/utils"
import { AGE_BRACKETS, SITUATION_OPTIONS, MOBILITY_OPTIONS } from "@/types"
import type { Analysis } from "@/types"
import { UploadCloud, FileText, ArrowRight, Check, ShieldCheck } from "lucide-react"

const schema = z.object({
  cv_text: z.string().min(200, "CV trop court (200 caractères minimum)."),
  cible_visee: z.string().min(50, "Cible trop courte (50 caractères minimum)."),
  prenom: z.string().min(1, "Prénom requis."),
  nom: z.string().min(1, "Nom requis."),
  tranche_age: z.string().min(1, "Tranche d’âge requise."),
  localisation: z.string().min(1, "Localisation requise."),
  situation_actuelle: z.string().min(1, "Situation requise."),
  type_mobilite: z.array(z.string()).min(1, "Type de mobilité requis."),
  notes_specifiques: z.string(),
})
type Fields = z.infer<typeof schema>

export default function NouvelleAnalysePage() {
  return (
    <Suspense>
      <NouvelleAnalyseForm />
    </Suspense>
  )
}

/** Section card with a numbered marker. */
function SectionCard({ n, title, hint, children }: { n: number; title: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl bg-card p-5 ring-1 ring-foreground/10 shadow-soft sm:p-6">
      <div className="mb-1 flex items-center gap-2.5">
        <span className="grid size-6 shrink-0 place-items-center rounded-md bg-orange-dark font-mono text-[11px] font-bold text-white">{n}</span>
        <h2 className="font-display text-base font-semibold text-navy">{title}</h2>
      </div>
      {hint && <p className="mb-3 pl-[2.1rem] text-xs text-muted-foreground">{hint}</p>}
      <div className={hint ? "" : "mt-3"}>{children}</div>
    </div>
  )
}

function NouvelleAnalyseForm() {
  const router = useRouter()
  const { user, loading: authLoading } = useAuth()
  const searchParams = useSearchParams()
  const [draftId, setDraftId] = useState<string | null>(searchParams.get("draft"))
  const [draftState, setDraftState] = useState<"idle" | "saving" | "saved" | "error" | "auth">("idle")
  const [uploadState, setUploadState] = useState<"idle" | "uploading" | "done" | "error">("idle")
  const [uploadedFilename, setUploadedFilename] = useState<string>("")
  const [projectUploadState, setProjectUploadState] = useState<"idle" | "uploading" | "done" | "error">("idle")
  const [projectUploadedFilename, setProjectUploadedFilename] = useState<string>("")
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [isProjectDragging, setIsProjectDragging] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  // Premium generation is offered only to users who are actually entitled to it
  // (paid plan or remaining credits). Everyone else generates the free tier and
  // unlocks the full report afterwards via /debloquer. This closes the free-premium hole.
  const canPremium = !!user && (user.plan === "paid" || (user.credits_remaining ?? 0) > 0)

  const { register, handleSubmit, control, setValue, watch, reset, formState: { errors } } = useForm<Fields>({
    resolver: zodResolver(schema),
    defaultValues: { notes_specifiques: "", tranche_age: "", situation_actuelle: "", type_mobilite: [] },
  })

  // Resume a saved draft (?draft=<id>)
  useEffect(() => {
    if (!draftId) return
    api.get<{ analysis: Analysis }>(`/analyses/${draftId}`, { skipRedirect: true })
      .then(({ analysis }) => {
        if (analysis.status !== "draft" || !analysis.inputs) return
        const i = analysis.inputs
        reset({
          cv_text: i.cv_text ?? "",
          cible_visee: i.cible_visee ?? "",
          prenom: i.prenom ?? "",
          nom: i.nom ?? "",
          tranche_age: i.tranche_age ?? "",
          localisation: i.localisation ?? "",
          situation_actuelle: i.situation_actuelle ?? "",
          type_mobilite: Array.isArray(i.type_mobilite) ? i.type_mobilite : i.type_mobilite ? [i.type_mobilite] : [],
          notes_specifiques: i.notes_specifiques ?? "",
        })
      })
      .catch(() => { /* draft gone — start blank */ })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

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

  const onSubmit = async (data: Fields) => {
    setSubmitError(null)
    setSubmitting(true)
    const tier = canPremium ? "sonnet" : "haiku"
    try {
      const res = await api.post<{ analysis: Analysis }>("/analyses/", { inputs: data, tier })
      if (draftId) api.delete(`/analyses/${draftId}`).catch(() => {})
      router.push(`/analyse/en-cours/${res.analysis.id}`)
    } catch (e) {
      setSubmitError(e instanceof ApiError ? e.message : "Erreur inattendue.")
      setSubmitting(false)
    }
  }

  const saveDraft = async () => {
    if (!authLoading && !user) { setDraftState("auth"); return }
    setDraftState("saving")
    try {
      const res = await api.post<{ analysis: Analysis }>(
        "/analyses/draft",
        { inputs: watch(), draft_id: draftId ?? undefined },
        { skipRedirect: true },
      )
      setDraftId(res.analysis.id)
      setDraftState("saved")
      setTimeout(() => setDraftState((s) => (s === "saved" ? "idle" : s)), 4000)
    } catch (e) {
      setDraftState(e instanceof ApiError && e.status === 401 ? "auth" : "error")
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

  return (
    <div className="min-h-screen bg-background">
      <AppBar />
      <div className="mx-auto max-w-3xl px-5 py-10 sm:px-8">
        <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
          <h1 className="font-display text-2xl font-bold text-navy">Nouvelle analyse</h1>
          <Badge variant="outline" className="font-mono text-xs">~2 min</Badge>
        </div>
        <p className="mb-8 text-sm text-muted-foreground">Tous les champs sont nécessaires pour déclencher l’analyse.</p>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {submitError && <Alert variant="destructive"><AlertDescription>{submitError}</AlertDescription></Alert>}

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
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-[1.2fr_1fr]">
              {dropZone("projet")}
              <div className="flex flex-col gap-1.5">
                <span className="text-center text-[10px] text-muted-foreground">— ou décrire librement —</span>
                <Textarea {...register("cible_visee")} placeholder="Intitulé du poste, description, programme de formation…" className="min-h-[104px] flex-1 resize-none bg-background text-sm" />
              </div>
            </div>
            {errors.cible_visee && <p className="mt-2 text-xs text-destructive">{errors.cible_visee.message}</p>}
          </SectionCard>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <SectionCard n={3} title="Votre profil">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="prenom">Prénom</Label>
                  <Input id="prenom" {...register("prenom")} placeholder="Marion" className="h-9" />
                  {errors.prenom && <p className="text-[10px] text-destructive">{errors.prenom.message}</p>}
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="nom">Nom</Label>
                  <Input id="nom" {...register("nom", { onChange: (e) => { e.target.value = e.target.value.toUpperCase() } })} placeholder="DUPONT" className="h-9 uppercase" />
                  {errors.nom && <p className="text-[10px] text-destructive">{errors.nom.message}</p>}
                </div>
                <div className="space-y-1.5">
                  <Label>Tranche d’âge</Label>
                  <Controller name="tranche_age" control={control} render={({ field }) => (
                    <Select onValueChange={field.onChange} value={field.value}>
                      <SelectTrigger className="h-9 w-full"><SelectValue placeholder="Sélectionner" /></SelectTrigger>
                      <SelectContent>{AGE_BRACKETS.map((a) => <SelectItem key={a} value={a}>{a}</SelectItem>)}</SelectContent>
                    </Select>
                  )} />
                  {errors.tranche_age && <p className="text-[10px] text-destructive">{errors.tranche_age.message}</p>}
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="localisation">Localisation</Label>
                  <Input id="localisation" {...register("localisation")} placeholder="Paris" className="h-9" />
                  {errors.localisation && <p className="text-[10px] text-destructive">{errors.localisation.message}</p>}
                </div>
                <div className="col-span-2 space-y-1.5">
                  <Label>Situation actuelle</Label>
                  <Controller name="situation_actuelle" control={control} render={({ field }) => (
                    <Select onValueChange={field.onChange} value={field.value}>
                      <SelectTrigger className="h-9 w-full"><SelectValue placeholder="Sélectionner" /></SelectTrigger>
                      <SelectContent>{SITUATION_OPTIONS.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
                    </Select>
                  )} />
                  {errors.situation_actuelle && <p className="text-[10px] text-destructive">{errors.situation_actuelle.message}</p>}
                </div>
              </div>
            </SectionCard>

            <SectionCard n={4} title="Vos préférences">
              <Controller name="type_mobilite" control={control} render={({ field }) => {
                const selected: string[] = Array.isArray(field.value) ? field.value : []
                const toggle = (opt: string) => field.onChange(selected.includes(opt) ? selected.filter((v) => v !== opt) : [...selected, opt])
                return (
                  <div>
                    <Label className="mb-1.5 block">Type de mobilité <span className="font-normal text-muted-foreground">· plusieurs choix possibles</span></Label>
                    <div className="flex flex-wrap gap-1.5">
                      {MOBILITY_OPTIONS.map((opt) => (
                        <button
                          key={opt}
                          type="button"
                          onClick={() => toggle(opt)}
                          aria-pressed={selected.includes(opt)}
                          aria-label={`Type de mobilité : ${opt}`}
                          className={cn(
                            "rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
                            selected.includes(opt)
                              ? "border-navy bg-navy text-white"
                              : "border-border bg-background text-navy hover:border-orange/50",
                          )}
                        >
                          {opt}
                        </button>
                      ))}
                    </div>
                  </div>
                )
              }} />
              {errors.type_mobilite && <p className="mt-1 text-[10px] text-destructive">{errors.type_mobilite.message}</p>}

              <div className="mt-4 space-y-1.5">
                <Label htmlFor="notes">Notes spécifiques</Label>
                <Textarea id="notes" {...register("notes_specifiques")} placeholder="RQTH, aidant, primo-arrivant, contraintes…" className="min-h-[72px] resize-none bg-secondary text-sm" />
              </div>
            </SectionCard>
          </div>

          {/* Footer */}
          <div className="flex flex-col gap-4 border-t border-border pt-5 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-col gap-1">
              <Button type="button" variant="outline" onClick={saveDraft} disabled={draftState === "saving"} className="self-start">
                {draftState === "saving" ? "Enregistrement…" : draftState === "saved" ? <><Check className="size-4 text-success" /> Brouillon enregistré</> : "Enregistrer le brouillon"}
              </Button>
              {draftState === "auth" && (
                <span className="text-xs text-destructive">
                  <Link href="/connexion" className="underline">Connectez-vous</Link> pour enregistrer un brouillon.
                </span>
              )}
              {draftState === "error" && <span className="text-xs text-destructive">Échec de l’enregistrement. Réessayez.</span>}
            </div>

            <Button type="submit" size="xl" disabled={submitting}>
              {submitting ? "Lancement…" : canPremium ? "Générer l’analyse complète" : "Générer mon analyse"}
              {!submitting && <ArrowRight />}
            </Button>
          </div>

          <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <ShieldCheck className="size-3.5 text-success" />
            {canPremium
              ? "Analyse complète · 9 sections. Données chiffrées, supprimables à tout moment."
              : "3 sections gratuites — les 6 suivantes après déblocage (9 € ou code conseiller). Données chiffrées."}
          </p>
        </form>
      </div>
    </div>
  )
}

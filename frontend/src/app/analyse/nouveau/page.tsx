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
import { UploadCloud, FileText } from "lucide-react"

const schema = z.object({
  cv_text:           z.string().min(200, "CV trop court (200 caractères minimum)."),
  cible_visee:       z.string().min(50, "Cible trop courte (50 caractères minimum)."),
  prenom:            z.string().min(1, "Prénom requis."),
  nom:               z.string().min(1, "Nom requis."),
  tranche_age:       z.string().min(1, "Tranche d'âge requise."),
  localisation:      z.string().min(1, "Localisation requise."),
  situation_actuelle:z.string().min(1, "Situation requise."),
  type_mobilite:     z.array(z.string()).min(1, "Type de mobilité requis."),
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
  const [submittingTier, setSubmittingTier] = useState<"haiku" | "sonnet" | null>(null)

  const { register, handleSubmit, control, setValue, watch, reset,
    formState: { errors } } = useForm<Fields>({
    resolver: zodResolver(schema),
    defaultValues: { notes_specifiques: "", tranche_age: "", situation_actuelle: "", type_mobilite: [] },
  })

  const cvText = watch("cv_text")

  // Resume a saved draft (?draft=<id>)
  useEffect(() => {
    if (!draftId) return
    api.get<{ analysis: Analysis }>(`/analyses/${draftId}`, { skipRedirect: true })
      .then(({ analysis }) => {
        if (analysis.status !== "draft" || !analysis.inputs) return
        const i = analysis.inputs
        reset({
          cv_text:            i.cv_text ?? "",
          cible_visee:        i.cible_visee ?? "",
          prenom:             i.prenom ?? "",
          nom:                i.nom ?? "",
          tranche_age:        i.tranche_age ?? "",
          localisation:       i.localisation ?? "",
          situation_actuelle: i.situation_actuelle ?? "",
          type_mobilite:      Array.isArray(i.type_mobilite) ? i.type_mobilite : i.type_mobilite ? [i.type_mobilite] : [],
          notes_specifiques:  i.notes_specifiques ?? "",
        })
      })
      .catch(() => { /* draft gone — start blank */ })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleFile = useCallback(async (file: File) => {
    if (file.type !== "application/pdf") {
      setUploadState("error"); return
    }
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
    if (file.type !== "application/pdf") {
      setProjectUploadState("error"); return
    }
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

  const onSubmit = async (data: Fields, tier: "haiku" | "sonnet") => {
    setSubmitError(null)
    setSubmittingTier(tier)
    try {
      const res = await api.post<{ analysis: Analysis }>("/analyses/", { inputs: data, tier })
      // The draft was launched — remove it so it doesn't linger in the space
      if (draftId) api.delete(`/analyses/${draftId}`).catch(() => {})
      router.push(`/analyse/en-cours/${res.analysis.id}`)
    } catch (e) {
      setSubmitError(e instanceof ApiError ? e.message : "Erreur inattendue.")
    } finally {
      setSubmittingTier(null)
    }
  }

  const saveDraft = async () => {
    if (!authLoading && !user) {
      setDraftState("auth")
      return
    }
    setDraftState("saving")
    try {
      const res = await api.post<{ analysis: Analysis }>(
        "/analyses/draft",
        { inputs: watch(), draft_id: draftId ?? undefined },
        { skipRedirect: true },
      )
      setDraftId(res.analysis.id)
      setDraftState("saved")
      setTimeout(() => setDraftState(s => (s === "saved" ? "idle" : s)), 4000)
    } catch (e) {
      setDraftState(e instanceof ApiError && e.status === 401 ? "auth" : "error")
    }
  }

  return (
    <div className="min-h-screen bg-background">
      <AppBar />
      <div className="max-w-[720px] mx-auto px-6 py-8">
        <div className="flex items-baseline justify-between mb-6">
          <h1 className="text-2xl font-bold">Nouvelle analyse</h1>
          <Badge variant="outline" className="font-mono text-xs">8 champs · ~2 min</Badge>
        </div>
        <p className="text-sm text-muted-foreground mb-8">
          Tous les champs sont nécessaires pour déclencher l'analyse.
        </p>

        <form onSubmit={e => e.preventDefault()} className="space-y-4">
          {submitError && <Alert variant="destructive"><AlertDescription>{submitError}</AlertDescription></Alert>}

          {/* ── Card 1 : CV ── */}
          <div className="rounded-lg border border-border bg-card p-5">
            <p className="font-semibold text-sm mb-3">① votre CV</p>
            <div className="grid grid-cols-[1.2fr_1fr] gap-3">
              {/* Drop zone */}
              <div
                onDrop={onDrop}
                onDragOver={e => { e.preventDefault(); setIsDragging(true) }}
                onDragLeave={() => setIsDragging(false)}
                onClick={() => document.getElementById("cv-file-input")?.click()}
                className={cn(
                  "flex flex-col items-center justify-center gap-2 rounded-md border-2 border-dashed h-32 cursor-pointer transition-colors",
                  isDragging ? "border-primary bg-primary/5" : "border-border bg-secondary hover:border-primary/50",
                  uploadState === "done" && "border-green-500/50 bg-green-50"
                )}
              >
                <input id="cv-file-input" type="file" accept="application/pdf" className="hidden"
                  onChange={e => e.target.files?.[0] && handleFile(e.target.files[0])} />
                {uploadState === "done" ? (
                  <>
                    <FileText className="h-5 w-5 text-green-600" />
                    <span className="text-xs text-green-700 font-medium">{uploadedFilename}</span>
                  </>
                ) : uploadState === "uploading" ? (
                  <span className="text-xs text-muted-foreground">Extraction en cours…</span>
                ) : (
                  <>
                    <UploadCloud className="h-5 w-5 text-muted-foreground" />
                    <span className="text-xs text-muted-foreground">déposer un PDF</span>
                    <span className="text-[10px] text-muted-foreground">glissez ici · ou cliquez</span>
                    <Badge variant="outline" className="text-[10px]">PDF · 10 Mo max</Badge>
                  </>
                )}
              </div>

              {/* Paste zone */}
              <div className="flex flex-col gap-1.5">
                <span className="text-[10px] text-muted-foreground text-center">— ou copier-coller le texte —</span>
                <Textarea
                  {...register("cv_text")}
                  placeholder="Collez le texte de votre CV ici…"
                  className="flex-1 text-xs resize-none min-h-[104px] bg-background"
                />
              </div>
            </div>
            {errors.cv_text && <p className="text-xs text-destructive mt-2">{errors.cv_text.message}</p>}
          </div>

          {/* ── Card 2 : Votre projet ── */}
          <div className="rounded-lg border border-border bg-card p-5">
            <p className="font-semibold text-sm mb-1">② votre projet</p>
            <p className="text-xs text-muted-foreground mb-3">offre d'emploi · fiche métier · programme de formation</p>
            <div className="grid grid-cols-[1.2fr_1fr] gap-3">
              {/* Drop zone */}
              <div
                onDrop={onProjectDrop}
                onDragOver={e => { e.preventDefault(); setIsProjectDragging(true) }}
                onDragLeave={() => setIsProjectDragging(false)}
                onClick={() => document.getElementById("projet-file-input")?.click()}
                className={cn(
                  "flex flex-col items-center justify-center gap-2 rounded-md border-2 border-dashed h-32 cursor-pointer transition-colors",
                  isProjectDragging ? "border-primary bg-primary/5" : "border-border bg-secondary hover:border-primary/50",
                  projectUploadState === "done" && "border-green-500/50 bg-green-50"
                )}
              >
                <input id="projet-file-input" type="file" accept="application/pdf" className="hidden"
                  onChange={e => e.target.files?.[0] && handleProjectFile(e.target.files[0])} />
                {projectUploadState === "done" ? (
                  <>
                    <FileText className="h-5 w-5 text-green-600" />
                    <span className="text-xs text-green-700 font-medium">{projectUploadedFilename}</span>
                  </>
                ) : projectUploadState === "uploading" ? (
                  <span className="text-xs text-muted-foreground">Extraction en cours…</span>
                ) : (
                  <>
                    <UploadCloud className="h-5 w-5 text-muted-foreground" />
                    <span className="text-xs text-muted-foreground">déposer un PDF</span>
                    <span className="text-[10px] text-muted-foreground">glissez ici · ou cliquez</span>
                    <Badge variant="outline" className="text-[10px]">PDF · 10 Mo max</Badge>
                  </>
                )}
              </div>

              {/* Paste zone */}
              <div className="flex flex-col gap-1.5">
                <span className="text-[10px] text-muted-foreground text-center">— ou décrire librement —</span>
                <Textarea
                  {...register("cible_visee")}
                  placeholder="Intitulé du poste, description, programme de formation…"
                  className="flex-1 text-xs resize-none min-h-[104px] bg-background"
                />
              </div>
            </div>
            {errors.cible_visee && <p className="text-xs text-destructive mt-2">{errors.cible_visee.message}</p>}
          </div>

          {/* ── Cards 3 & 4 side by side ── */}
          <div className="grid grid-cols-2 gap-4">
            {/* Card 3 : Qui êtes-vous */}
            <div className="rounded-lg border border-border bg-card p-5">
              <p className="font-semibold text-sm mb-3">③ qui êtes-vous</p>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="text-xs">Prénom</Label>
                  <Input {...register("prenom")} placeholder="Marion" className="h-8 text-xs" />
                  {errors.prenom && <p className="text-[10px] text-destructive">{errors.prenom.message}</p>}
                </div>

                <div className="space-y-1">
                  <Label className="text-xs">Nom</Label>
                  <Input
                    {...register("nom", {
                      onChange: e => { e.target.value = e.target.value.toUpperCase() },
                    })}
                    placeholder="DUPONT"
                    className="h-8 text-xs uppercase"
                  />
                  {errors.nom && <p className="text-[10px] text-destructive">{errors.nom.message}</p>}
                </div>

                <div className="space-y-1">
                  <Label className="text-xs">Tranche d'âge</Label>
                  <Controller name="tranche_age" control={control} render={({ field }) => (
                    <Select onValueChange={field.onChange} value={field.value}>
                      <SelectTrigger className="h-8 text-xs"><SelectValue placeholder="Sélectionner" /></SelectTrigger>
                      <SelectContent>{AGE_BRACKETS.map(a => <SelectItem key={a} value={a} className="text-xs">{a}</SelectItem>)}</SelectContent>
                    </Select>
                  )} />
                  {errors.tranche_age && <p className="text-[10px] text-destructive">{errors.tranche_age.message}</p>}
                </div>

                <div className="space-y-1">
                  <Label className="text-xs">Localisation</Label>
                  <Input {...register("localisation")} placeholder="Paris" className="h-8 text-xs" />
                  {errors.localisation && <p className="text-[10px] text-destructive">{errors.localisation.message}</p>}
                </div>

                <div className="space-y-1">
                  <Label className="text-xs">Situation actuelle</Label>
                  <Controller name="situation_actuelle" control={control} render={({ field }) => (
                    <Select onValueChange={field.onChange} value={field.value}>
                      <SelectTrigger className="h-8 text-xs"><SelectValue placeholder="Sélectionner" /></SelectTrigger>
                      <SelectContent>{SITUATION_OPTIONS.map(s => <SelectItem key={s} value={s} className="text-xs">{s}</SelectItem>)}</SelectContent>
                    </Select>
                  )} />
                  {errors.situation_actuelle && <p className="text-[10px] text-destructive">{errors.situation_actuelle.message}</p>}
                </div>
              </div>
            </div>

            {/* Card 4 : Mobilité + Notes */}
            <div className="rounded-lg border border-border bg-card p-5">
              <p className="font-semibold text-sm mb-2">④ type de mobilité</p>
              <Controller name="type_mobilite" control={control} render={({ field }) => {
                const selected: string[] = Array.isArray(field.value) ? field.value : []
                const toggle = (opt: string) =>
                  field.onChange(selected.includes(opt) ? selected.filter(v => v !== opt) : [...selected, opt])
                return (
                  <>
                    <p className="text-[10px] text-muted-foreground mb-1.5">Plusieurs réponses possibles</p>
                    <div className="flex flex-wrap gap-1.5">
                      {MOBILITY_OPTIONS.map(opt => (
                        <button key={opt} type="button"
                          onClick={() => toggle(opt)}
                          className={cn(
                            "px-2.5 py-1 rounded-full border text-xs transition-colors",
                            selected.includes(opt)
                              ? "bg-primary border-primary text-primary-foreground"
                              : "bg-background border-border text-foreground hover:border-primary/50"
                          )}>
                          {opt}
                        </button>
                      ))}
                    </div>
                  </>
                )
              }} />
              {errors.type_mobilite && <p className="text-[10px] text-destructive mt-1">{errors.type_mobilite.message}</p>}

              <p className="font-semibold text-sm mt-3 mb-1.5">⑤ notes spécifiques</p>
              <Textarea
                {...register("notes_specifiques")}
                placeholder="RQTH, aidant, primo-arrivant, contraintes…"
                className="min-h-[54px] text-xs bg-secondary resize-none"
              />
            </div>
          </div>

          {/* ── Footer bar ── */}
          <div className="flex items-center justify-between pt-2">
            <span className="text-[11px] text-muted-foreground">
              données stockées chiffrées · supprimables à tout moment
            </span>
            <div className="flex gap-2 items-center">
              <div className="flex flex-col items-end gap-1">
                <Button type="button" variant="outline" size="sm" onClick={saveDraft}
                  disabled={draftState === "saving"}>
                  {draftState === "saving" ? "enregistrement…"
                    : draftState === "saved" ? "✓ brouillon enregistré"
                    : "enregistrer brouillon"}
                </Button>
                {draftState === "auth" && (
                  <span className="text-[10px] text-destructive">
                    <Link href="/connexion" className="underline">Connectez-vous</Link> pour enregistrer un brouillon.
                  </span>
                )}
                {draftState === "error" && (
                  <span className="text-[10px] text-destructive">Échec de l&apos;enregistrement. Réessayez.</span>
                )}
              </div>
              <div className="flex gap-3">
                <button
                  type="button"
                  disabled={submittingTier !== null}
                  onClick={handleSubmit(data => onSubmit(data, "haiku"))}
                  className="group flex flex-col items-start gap-1 rounded-md border border-amber-200 bg-amber-50 px-4 py-2 text-left transition hover:bg-amber-100 disabled:opacity-50"
                >
                  <span className="text-sm font-semibold text-amber-800">
                    {submittingTier === "haiku" ? "Lancement…" : "👉 Clique ici pour générer la version gratuite"}
                  </span>
                  <span className="text-[11px] text-amber-700/80">
                    Si tu cliques ce bouton, tu verras exactement ce qu&apos;un utilisateur gratuit verra.
                  </span>
                </button>
                <button
                  type="button"
                  disabled={submittingTier !== null}
                  onClick={handleSubmit(data => onSubmit(data, "sonnet"))}
                  className="group flex flex-col items-start gap-1 rounded-md border border-primary/30 bg-primary/5 px-4 py-2 text-left transition hover:bg-primary hover:text-primary-foreground disabled:opacity-50"
                >
                  <span className="text-sm font-semibold">
                    {submittingTier === "sonnet" ? "Lancement…" : "👉 Clique ici pour générer la version premium"}
                  </span>
                  <span className="text-[11px] opacity-70">
                    Si tu cliques ce bouton, tu verras exactement ce qu&apos;un utilisateur premium verra.
                  </span>
                </button>
              </div>
            </div>
          </div>
        </form>
      </div>
    </div>
  )
}

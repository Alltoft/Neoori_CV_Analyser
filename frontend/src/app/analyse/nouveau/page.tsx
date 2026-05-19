"use client"

import { useState, useCallback } from "react"
import { useRouter } from "next/navigation"
import { useForm, Controller } from "react-hook-form"
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
  tranche_age:       z.string().min(1, "Tranche d'âge requise."),
  localisation:      z.string().min(1, "Localisation requise."),
  situation_actuelle:z.string().min(1, "Situation requise."),
  type_mobilite:     z.string().min(1, "Type de mobilité requis."),
  notes_specifiques: z.string(),
})
type Fields = z.infer<typeof schema>

export default function NouvelleAnalysePage() {
  const router = useRouter()
  const [uploadState, setUploadState] = useState<"idle" | "uploading" | "done" | "error">("idle")
  const [uploadedFilename, setUploadedFilename] = useState<string>("")
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [submittingTier, setSubmittingTier] = useState<"haiku" | "sonnet" | null>(null)

  const { register, handleSubmit, control, setValue, watch,
    formState: { errors } } = useForm<Fields>({
    resolver: zodResolver(schema),
    defaultValues: { notes_specifiques: "", tranche_age: "", situation_actuelle: "" },
  })

  const cvText = watch("cv_text")

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

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setIsDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }, [handleFile])

  const onSubmit = async (data: Fields, tier: "haiku" | "sonnet") => {
    setSubmitError(null)
    setSubmittingTier(tier)
    try {
      const res = await api.post<{ analysis: Analysis }>("/analyses/", { inputs: data, tier })
      router.push(`/analyse/en-cours/${res.analysis.id}`)
    } catch (e) {
      setSubmitError(e instanceof ApiError ? e.message : "Erreur inattendue.")
    } finally {
      setSubmittingTier(null)
    }
  }

  const saveDraft = async () => {
    const data = watch()
    try {
      await api.post("/analyses/draft", { inputs: data })
    } catch { /* silent */ }
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

          {/* ── Card 2 : Cible ── */}
          <div className="rounded-lg border border-border bg-card p-5">
            <p className="font-semibold text-sm mb-1">② cible visée</p>
            <p className="text-xs text-muted-foreground mb-1">offre d'emploi · fiche métier · programme de formation</p>
            <p className="text-[11px] text-muted-foreground/70 mb-2">Ex. : « Chargé(e) de projet RSE en secteur associatif, CDI, Île-de-France — poste impliquant la coordination de partenaires et le suivi d'indicateurs d'impact. »</p>
            <Textarea
              {...register("cible_visee")}
              placeholder="Collez l'intitulé et la description du poste visé, ou décrivez librement votre cible…"
              className="min-h-[88px] bg-secondary text-sm"
            />
            {errors.cible_visee && <p className="text-xs text-destructive mt-1.5">{errors.cible_visee.message}</p>}
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
              <Controller name="type_mobilite" control={control} render={({ field }) => (
                <div className="flex flex-wrap gap-1.5">
                  {MOBILITY_OPTIONS.map(opt => (
                    <button key={opt} type="button"
                      onClick={() => field.onChange(opt)}
                      className={cn(
                        "px-2.5 py-1 rounded-full border text-xs transition-colors",
                        field.value === opt
                          ? "bg-primary border-primary text-primary-foreground"
                          : "bg-background border-border text-foreground hover:border-primary/50"
                      )}>
                      {opt}
                    </button>
                  ))}
                </div>
              )} />
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
              <Button type="button" variant="outline" size="sm" onClick={saveDraft}>
                enregistrer brouillon
              </Button>
              <div className="flex rounded-md border border-border overflow-hidden">
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="rounded-none border-r border-border text-xs h-8 px-4 hover:bg-amber-50 hover:text-amber-700"
                  disabled={submittingTier !== null}
                  onClick={handleSubmit(data => onSubmit(data, "haiku"))}
                >
                  {submittingTier === "haiku" ? "Lancement…" : "Haiku · §1–4"}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="rounded-none text-xs h-8 px-4 bg-primary/5 hover:bg-primary hover:text-primary-foreground"
                  disabled={submittingTier !== null}
                  onClick={handleSubmit(data => onSubmit(data, "sonnet"))}
                >
                  {submittingTier === "sonnet" ? "Lancement…" : "Sonnet · §1–9"}
                </Button>
              </div>
            </div>
          </div>
        </form>
      </div>
    </div>
  )
}

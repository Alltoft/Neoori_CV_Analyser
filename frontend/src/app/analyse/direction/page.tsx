"use client"

import { useCallback, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { ArrowRight, FileText, UploadCloud } from "lucide-react"

import { AppBar } from "@/components/layout/AppBar"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { SectionCard } from "@/components/ui/section-card"
import { Textarea } from "@/components/ui/textarea"
import { api, ApiError } from "@/lib/api"
import { cn } from "@/lib/utils"
import type { Analysis } from "@/types"

/**
 * Parcours 2 — « Je cherche ma direction ».
 *
 * Three questions, not four. The CDC listed non-negotiable constraints as a
 * fourth, but those already live in bloc 4 of the Profil de base and health is
 * covered for everyone by bloc 5 — so it was re-asking what the profile knew.
 * "Quatre questions à trois, un abandon en moins." (Parcours doc §5)
 */
const QUESTIONS = [
  {
    name: "satisfaction" as const,
    label: "Qu'est-ce qui vous a donné le plus de satisfaction dans votre parcours ?",
    hint: "Un moment, une mission, un environnement.",
  },
  {
    name: "refus" as const,
    label: "Qu'est-ce que vous ne voulez plus faire, ou ce qui ne vous convient plus aujourd'hui ?",
    hint: "",
  },
  {
    name: "raison_changement" as const,
    label: "La raison principale de votre changement ?",
    hint: "Un choix personnel, une évolution de votre secteur, autre.",
  },
]

const schema = z.object({
  cv_text: z.string().min(200, "CV ou liste d'expériences trop courte (200 caractères minimum)."),
  satisfaction: z.string().min(20, "Réponse trop courte (20 caractères minimum)."),
  refus: z.string().min(20, "Réponse trop courte (20 caractères minimum)."),
  raison_changement: z.string().min(20, "Réponse trop courte (20 caractères minimum)."),
})
type Fields = z.infer<typeof schema>

export default function DirectionPage() {
  const router = useRouter()
  const [uploadState, setUploadState] = useState<"idle" | "uploading" | "done" | "error">("idle")
  const [filename, setFilename] = useState("")
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const { register, handleSubmit, setValue, formState: { errors } } = useForm<Fields>({
    resolver: zodResolver(schema),
    defaultValues: { cv_text: "", satisfaction: "", refus: "", raison_changement: "" },
  })

  const handleFile = useCallback(async (file: File) => {
    if (file.type !== "application/pdf") { setUploadState("error"); return }
    setUploadState("uploading")
    const fd = new FormData()
    fd.append("file", file)
    try {
      const res = await api.upload<{ cv_text: string }>("/upload/cv", fd)
      setValue("cv_text", res.cv_text, { shouldValidate: true })
      setFilename(file.name)
      setUploadState("done")
    } catch {
      setUploadState("error")
    }
  }, [setValue])

  const onSubmit = async (data: Fields) => {
    setSubmitError(null)
    setSubmitting(true)
    try {
      const res = await api.post<{ analysis: Analysis }>("/analyses/", {
        inputs: { ...data, _path: "2" },
      })
      router.push(`/analyse/en-cours/${res.analysis.id}`)
    } catch (e) {
      setSubmitError(e instanceof ApiError ? e.message : "Erreur inattendue.")
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-secondary">
      <AppBar />
      {/* Same accent as this parcours' card on the landing — the colour is
          how someone knows they are still in the scenario they picked. */}
      <div className="bg-navy h-1.5 w-full" role="presentation" aria-hidden />
      <div className="mx-auto max-w-2xl px-4 py-8">
        <div className="mb-6">
          <p className="eyebrow text-orange-dark">Parcours 2</p>
          <h1 className="mt-1 font-display text-2xl font-bold text-navy sm:text-3xl">
            Je cherche ma direction
          </h1>
          <p className="mt-1.5 text-sm text-muted-foreground">
            Trois questions, après votre CV. On part de ce que vous avez déjà construit.
          </p>
        </div>

        {submitError && (
          <Alert variant="destructive" className="mb-4">
            <AlertDescription>{submitError}</AlertDescription>
          </Alert>
        )}

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
          <SectionCard
            n={1}
            title="Votre parcours"
            hint="Un CV, ou simplement la liste de vos expériences en vrac — les deux marchent."
          >
            <div
              onClick={() => document.getElementById("cv-file")?.click()}
              onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) handleFile(f) }}
              onDragOver={(e) => e.preventDefault()}
              className={cn(
                "mb-3 flex cursor-pointer items-center gap-3 rounded-xl border border-dashed border-input p-4 transition-colors hover:border-orange/50",
                uploadState === "done" && "border-success/40 bg-success/5",
                uploadState === "error" && "border-destructive/40",
              )}
            >
              {uploadState === "done"
                ? <FileText className="size-4 shrink-0 text-success" />
                : <UploadCloud className="size-4 shrink-0 text-muted-foreground" />}
              <span className="text-xs text-muted-foreground">
                {uploadState === "uploading" && "Lecture du CV…"}
                {uploadState === "done" && filename}
                {uploadState === "error" && "PDF illisible. Collez plutôt le texte ci-dessous."}
                {uploadState === "idle" && "Glissez un PDF ici, ou cliquez pour choisir."}
              </span>
              <input id="cv-file" type="file" accept="application/pdf" className="hidden"
                     onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f) }} />
            </div>
            <Textarea rows={7} placeholder="…ou collez votre CV / vos expériences ici." {...register("cv_text")} />
            {errors.cv_text && <p className="mt-1 text-[10px] text-destructive">{errors.cv_text.message}</p>}
          </SectionCard>

          {QUESTIONS.map((q, i) => (
            <SectionCard key={q.name} n={i + 2} title={q.label} hint={q.hint || undefined}>
              <Textarea rows={4} {...register(q.name)} />
              {errors[q.name] && (
                <p className="mt-1 text-[10px] text-destructive">{errors[q.name]?.message}</p>
              )}
            </SectionCard>
          ))}

          <div className="flex flex-col items-start justify-between gap-3 rounded-2xl bg-card p-5 ring-1 ring-foreground/10 sm:flex-row sm:items-center">
            <p className="text-xs text-muted-foreground">
              Pas encore de profil ?{" "}
              <Link href="/profil" className="link-underline text-navy">Le compléter</Link>{" "}
              rend le rapport nettement plus précis.
            </p>
            <Button type="submit" size="lg" disabled={submitting}>
              {submitting ? "Envoi…" : "Lancer l'analyse"} <ArrowRight className="size-4" />
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}

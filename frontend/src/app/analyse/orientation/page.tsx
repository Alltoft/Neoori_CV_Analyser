"use client"

import { useState, useCallback } from "react"
import { useRouter } from "next/navigation"
import { AppBar } from "@/components/layout/AppBar"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Separator } from "@/components/ui/separator"
import { api, ApiError } from "@/lib/api"
import { cn } from "@/lib/utils"
import type { Analysis, SubProfile } from "@/types"
import { UploadCloud, FileText, ArrowLeft, ArrowRight } from "lucide-react"

const AIME_OPTIONS = [
  "Aider, accompagner, prendre soin des autres",
  "Organiser, planifier, structurer",
  "Créer, concevoir, imaginer",
  "Enseigner, transmettre, expliquer",
  "Analyser, résoudre des problèmes, chercher",
  "Construire, fabriquer, travailler de ses mains",
] as const

const COMPETENT_OPTIONS = [
  "Quand je gère une situation d'urgence ou de crise",
  "Quand j'explique quelque chose de compliqué simplement",
  "Quand je coordonne des personnes différentes",
  "Quand je dois trouver une solution créative",
  "Quand je prends soin de quelqu'un de vulnérable",
  "Quand je mène un projet du début à la fin",
] as const

const REFUSE_OPTIONS = [
  "Travailler seul(e), sans contact humain",
  "Travailler en open space ou en milieu très bruyant",
  "Travailler sous pression permanente",
  "Faire un travail répétitif sans créativité",
  "Travailler en extérieur ou avec contraintes physiques fortes",
] as const

const PAUSE_OPTIONS = [
  "Vie de famille / garde des enfants",
  "Accompagnement d'un proche (aidant)",
  "Problème de santé personnel",
  "Projet personnel (formation, création, voyage…)",
  "Autre",
] as const

const CONTRAINTES_B2_OPTIONS = [
  "Disponibilité horaire limitée (temps partiel uniquement)",
  "Nécessité de rester proche de chez moi",
  "Télétravail indispensable ou fortement souhaité",
  "Aucune contrainte particulière",
] as const

const CONTRAINTES_B3_OPTIONS = [
  "Fatigue — je ne peux pas travailler à temps plein immédiatement",
  "Mobilité — certains déplacements ou postures sont difficiles",
  "Concentration — les environnements très stimulants sont épuisants",
  "Communication — certains contextes sociaux sont difficiles",
] as const

const ACCOMPAGNEMENT_OPTIONS = [
  "Oui — Cap Emploi",
  "Oui — Mission Locale",
  "Oui — autre structure (SAMETH, CRP, UEROS…)",
  "Non, et je souhaite être mis(e) en relation",
  "Non, je préfère avancer seul(e) pour l'instant",
] as const

const SUB_PROFILES: { value: SubProfile; title: string; desc: string }[] = [
  { value: "b1", title: "Jeune en insertion", desc: "Peu ou pas d'expérience professionnelle" },
  { value: "b2", title: "Reprise après pause", desc: "Vie de famille, aidant, arrêt longue durée" },
  { value: "b3", title: "Reprise après maladie ou handicap", desc: "Avec contraintes de santé à prendre en compte" },
]

type FormState = {
  nom: string
  aime: string[]
  competent: string[]
  refuse: string[]
  pause_activite: string
  contraintes_pratiques: string[]
  contraintes_b3: string[]
  accompagnement: string
  cv_b3: string
  consent: boolean
}

const EMPTY: FormState = {
  nom: "",
  aime: [],
  competent: [],
  refuse: [],
  pause_activite: "",
  contraintes_pratiques: [],
  contraintes_b3: [],
  accompagnement: "",
  cv_b3: "",
  consent: false,
}

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "px-3 py-1.5 rounded-full border text-xs text-left transition-colors",
        active
          ? "bg-orange border-orange text-white"
          : "bg-background border-border text-foreground hover:border-orange/50",
      )}
    >
      {children}
    </button>
  )
}

export default function OrientationPage() {
  const router = useRouter()
  const [step, setStep] = useState<number>(0)
  const [sub, setSub] = useState<SubProfile | null>(null)
  const [form, setForm] = useState<FormState>(EMPTY)
  const [uploadState, setUploadState] = useState<"idle" | "uploading" | "done" | "error">("idle")
  const [uploadedFilename, setUploadedFilename] = useState("")
  const [isDragging, setIsDragging] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  const toggleMulti = (key: "aime" | "competent" | "refuse" | "contraintes_pratiques" | "contraintes_b3", value: string) => {
    setForm(f => {
      const arr = f[key]
      return { ...f, [key]: arr.includes(value) ? arr.filter(v => v !== value) : [...arr, value] }
    })
  }

  const handleCvFile = useCallback(async (file: File) => {
    if (file.type !== "application/pdf") { setUploadState("error"); return }
    setUploadState("uploading")
    const fd = new FormData()
    fd.append("file", file)
    try {
      const res = await api.upload<{ cv_text: string }>("/upload/cv", fd)
      setForm(f => ({ ...f, cv_b3: res.cv_text }))
      setUploadedFilename(file.name)
      setUploadState("done")
    } catch {
      setUploadState("error")
    }
  }, [])

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setIsDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleCvFile(file)
  }, [handleCvFile])

  // Step structure:
  //   B1 → 0 sub-select, 1 common, 2 consent  (3 visible steps)
  //   B2 → 0 sub-select, 1 common, 2 B2,      3 consent
  //   B3 → 0 sub-select, 1 common, 2 B3,      3 consent
  const totalSteps = sub === "b1" ? 3 : 4

  const canNext = (): boolean => {
    if (step === 0) return sub !== null
    if (step === 1) {
      return form.nom.trim().length > 0 && form.aime.length > 0 && form.competent.length > 0
    }
    if (step === 2 && sub === "b2") return form.pause_activite.length > 0
    if (step === 2 && sub === "b3") return form.accompagnement.length > 0
    // consent step
    return form.consent
  }

  const next = () => setStep(s => Math.min(s + 1, totalSteps - 1))
  const back = () => setStep(s => Math.max(s - 1, 0))

  const submit = async () => {
    if (!sub) return
    setSubmitting(true)
    setSubmitError(null)
    const payload = {
      inputs: {
        _path: "B",
        _sub_profile: sub,
        nom: form.nom.trim(),
        aime: form.aime,
        competent: form.competent,
        refuse: form.refuse,
        ...(sub === "b2" && {
          pause_activite: form.pause_activite,
          contraintes_pratiques: form.contraintes_pratiques,
        }),
        ...(sub === "b3" && {
          contraintes_b3: form.contraintes_b3,
          accompagnement: form.accompagnement,
          cv_b3: form.cv_b3,
        }),
      },
    }
    try {
      const res = await api.post<{ analysis: Analysis }>("/analyses/", payload)
      router.push(`/analyse/en-cours/${res.analysis.id}`)
    } catch (e) {
      setSubmitError(e instanceof ApiError ? e.message : "Erreur inattendue.")
    } finally {
      setSubmitting(false)
    }
  }

  const isLastStep = step === totalSteps - 1

  return (
    <div className="min-h-screen bg-background">
      <AppBar />
      <div className="max-w-[720px] mx-auto px-6 py-8">
        <p className="font-mono text-[11px] tracking-[0.15em] uppercase text-orange mb-2">Chemin B · Orientation</p>
        <div className="flex items-baseline justify-between mb-6">
          <h1 className="font-display text-2xl font-bold text-navy">Portrait de potentiel</h1>
          <Badge variant="outline" className="font-mono text-xs">
            étape {step + 1} / {totalSteps}
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground mb-8">
          Quelques questions pour identifier vos points d&apos;appui et des pistes compatibles avec votre situation.
        </p>

        {submitError && (
          <Alert variant="destructive" className="mb-4"><AlertDescription>{submitError}</AlertDescription></Alert>
        )}

        {/* ── Step 0 — Sub-profile ── */}
        {step === 0 && (
          <div className="space-y-3">
            <p className="font-display font-semibold text-sm text-navy">Quelle situation décrit le mieux votre point de départ ?</p>
            <div className="grid grid-cols-1 gap-3">
              {SUB_PROFILES.map(p => (
                <button
                  key={p.value}
                  type="button"
                  onClick={() => setSub(p.value)}
                  className={cn(
                    "rounded-xl border p-5 text-left transition-all hover-lift",
                    sub === p.value
                      ? "border-orange bg-orange/5"
                      : "border-border bg-card hover:border-orange/50",
                  )}
                >
                  <span className="inline-flex items-center justify-center px-2 h-5 rounded-md bg-orange text-white text-[10px] font-mono font-bold uppercase tracking-widest">
                    {p.value.toUpperCase()}
                  </span>
                  <p className="mt-2 font-display font-semibold text-base text-navy">{p.title}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{p.desc}</p>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ── Step 1 — Common questions ── */}
        {step === 1 && (
          <div className="space-y-6">
            <div className="rounded-xl border border-border bg-card p-5">
              <Label className="font-display text-sm font-semibold text-navy flex items-center">
                <span className="inline-flex items-center justify-center w-5 h-5 rounded-md bg-orange text-white text-[10px] font-mono font-bold mr-2 shrink-0">1</span>
                Votre prénom et nom
              </Label>
              <Input
                value={form.nom}
                onChange={e => setForm(f => ({ ...f, nom: e.target.value }))}
                placeholder="Prénom NOM"
                className="mt-2 h-9 text-sm"
              />
            </div>

            <div className="rounded-xl border border-border bg-card p-5">
              <p className="font-display text-sm font-semibold text-navy flex items-center">
                <span className="inline-flex items-center justify-center w-5 h-5 rounded-md bg-orange text-white text-[10px] font-mono font-bold mr-2 shrink-0">2</span>
                Qu&apos;est-ce que vous aimez faire — même hors travail ?
              </p>
              <p className="text-[11px] text-muted-foreground mt-0.5 mb-3">Choisissez tout ce qui vous correspond</p>
              <div className="flex flex-wrap gap-1.5">
                {AIME_OPTIONS.map(opt => (
                  <Chip key={opt} active={form.aime.includes(opt)} onClick={() => toggleMulti("aime", opt)}>{opt}</Chip>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-border bg-card p-5">
              <p className="font-display text-sm font-semibold text-navy flex items-center">
                <span className="inline-flex items-center justify-center w-5 h-5 rounded-md bg-orange text-white text-[10px] font-mono font-bold mr-2 shrink-0">3</span>
                Dans quelles situations vous sentez-vous compétent(e) ?
              </p>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {COMPETENT_OPTIONS.map(opt => (
                  <Chip key={opt} active={form.competent.includes(opt)} onClick={() => toggleMulti("competent", opt)}>{opt}</Chip>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-border bg-card p-5">
              <p className="font-display text-sm font-semibold text-navy flex items-center">
                <span className="inline-flex items-center justify-center w-5 h-5 rounded-md bg-orange text-white text-[10px] font-mono font-bold mr-2 shrink-0">4</span>
                Qu&apos;est-ce que vous refusez catégoriquement dans un travail ?
              </p>
              <p className="text-[11px] text-muted-foreground mt-0.5 mb-3">Optionnel</p>
              <div className="flex flex-wrap gap-1.5">
                {REFUSE_OPTIONS.map(opt => (
                  <Chip key={opt} active={form.refuse.includes(opt)} onClick={() => toggleMulti("refuse", opt)}>{opt}</Chip>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── Step 2 — B2 specific ── */}
        {step === 2 && sub === "b2" && (
          <div className="space-y-6">
            <div className="rounded-xl border border-border bg-card p-5">
              <p className="font-display text-sm font-semibold text-navy flex items-center">
                <span className="inline-flex items-center justify-center w-5 h-5 rounded-md bg-orange text-white text-[10px] font-mono font-bold mr-2 shrink-0">1</span>
                Quelle a été votre principale activité pendant la pause ?
              </p>
              <div className="mt-3 flex flex-col gap-2">
                {PAUSE_OPTIONS.map(opt => (
                  <Chip key={opt} active={form.pause_activite === opt} onClick={() => setForm(f => ({ ...f, pause_activite: opt }))}>{opt}</Chip>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-border bg-card p-5">
              <p className="font-display text-sm font-semibold text-navy flex items-center">
                <span className="inline-flex items-center justify-center w-5 h-5 rounded-md bg-orange text-white text-[10px] font-mono font-bold mr-2 shrink-0">2</span>
                Avez-vous des contraintes pratiques pour reprendre ?
              </p>
              <p className="text-[11px] text-muted-foreground mt-0.5 mb-3">Optionnel</p>
              <div className="flex flex-wrap gap-1.5">
                {CONTRAINTES_B2_OPTIONS.map(opt => (
                  <Chip key={opt} active={form.contraintes_pratiques.includes(opt)} onClick={() => toggleMulti("contraintes_pratiques", opt)}>{opt}</Chip>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── Step 2 — B3 specific ── */}
        {step === 2 && sub === "b3" && (
          <div className="space-y-6">
            <Alert>
              <AlertDescription className="text-xs">
                Ces questions ne demandent jamais votre diagnostic ni la nature de votre handicap.
                Elles servent uniquement à filtrer des pistes compatibles avec votre réalité.
              </AlertDescription>
            </Alert>

            <div className="rounded-xl border border-border bg-card p-5">
              <p className="font-display text-sm font-semibold text-navy flex items-center">
                <span className="inline-flex items-center justify-center w-5 h-5 rounded-md bg-orange text-white text-[10px] font-mono font-bold mr-2 shrink-0">1</span>
                Avez-vous un CV à partager ?
              </p>
              <p className="text-[11px] text-muted-foreground mt-0.5 mb-3">
                Optionnel — Si vous avez déjà travaillé, vos expériences passées permettent d&apos;identifier des compétences transférables, même si elles datent.
              </p>
              <div className="grid grid-cols-[1.2fr_1fr] gap-3">
                <div
                  onDrop={onDrop}
                  onDragOver={e => { e.preventDefault(); setIsDragging(true) }}
                  onDragLeave={() => setIsDragging(false)}
                  onClick={() => document.getElementById("cv-b3-input")?.click()}
                  className={cn(
                    "flex flex-col items-center justify-center gap-2 rounded-md border-2 border-dashed h-28 cursor-pointer transition-colors",
                    isDragging ? "border-orange bg-orange/5" : "border-border bg-secondary hover:border-orange/50",
                    uploadState === "done" && "border-green-500/50 bg-green-50",
                  )}
                >
                  <input id="cv-b3-input" type="file" accept="application/pdf" className="hidden"
                    onChange={e => e.target.files?.[0] && handleCvFile(e.target.files[0])} />
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
                      <Badge variant="outline" className="text-[10px]">PDF · 10 Mo max</Badge>
                    </>
                  )}
                </div>
                <Textarea
                  value={form.cv_b3}
                  onChange={e => setForm(f => ({ ...f, cv_b3: e.target.value }))}
                  placeholder="… ou collez votre CV / vos expériences"
                  className="text-xs resize-none min-h-[112px] bg-background"
                />
              </div>
            </div>

            <div className="rounded-xl border border-border bg-card p-5">
              <p className="font-display text-sm font-semibold text-navy flex items-center">
                <span className="inline-flex items-center justify-center w-5 h-5 rounded-md bg-orange text-white text-[10px] font-mono font-bold mr-2 shrink-0">2</span>
                Quelles sont les contraintes que vous souhaitez prendre en compte ?
              </p>
              <p className="text-[11px] text-muted-foreground mt-0.5 mb-3">Optionnel</p>
              <div className="flex flex-wrap gap-1.5">
                {CONTRAINTES_B3_OPTIONS.map(opt => (
                  <Chip key={opt} active={form.contraintes_b3.includes(opt)} onClick={() => toggleMulti("contraintes_b3", opt)}>{opt}</Chip>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-border bg-card p-5">
              <p className="font-display text-sm font-semibold text-navy flex items-center">
                <span className="inline-flex items-center justify-center w-5 h-5 rounded-md bg-orange text-white text-[10px] font-mono font-bold mr-2 shrink-0">3</span>
                Êtes-vous déjà accompagné(e) par une structure spécialisée ?
              </p>
              <div className="mt-3 flex flex-col gap-2">
                {ACCOMPAGNEMENT_OPTIONS.map(opt => (
                  <Chip key={opt} active={form.accompagnement === opt} onClick={() => setForm(f => ({ ...f, accompagnement: opt }))}>{opt}</Chip>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── Final step — consent ── */}
        {isLastStep && (
          <div className="space-y-5">
            <div className="rounded-xl overflow-hidden border border-border flex">
              <div className="w-1.5 bg-orange shrink-0" />
              <div className="bg-peach-soft px-4 py-3 flex-1">
                <p className="font-mono text-[10px] font-bold tracking-[0.15em] uppercase text-orange mb-1">Confidentialité</p>
                <p className="text-xs text-navy/70 leading-relaxed">
                  Vos réponses sont utilisées uniquement pour produire cette analyse et vous faire des suggestions.
                  Elles ne sont pas partagées avec des tiers ni utilisées pour entraîner des modèles d&apos;IA.
                  Vous pouvez supprimer votre analyse à tout moment.
                </p>
              </div>
            </div>
            <label className="flex items-start gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={form.consent}
                onChange={e => setForm(f => ({ ...f, consent: e.target.checked }))}
                className="mt-1 h-4 w-4 accent-orange"
              />
              <span className="text-sm">
                Je confirme avoir lu et accepté la note de confidentialité.
              </span>
            </label>
          </div>
        )}

        <Separator className="my-8" />

        {/* ── Navigation ── */}
        <div className="flex items-center justify-between">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={back}
            disabled={step === 0 || submitting}
          >
            <ArrowLeft className="h-4 w-4 mr-1.5" /> retour
          </Button>
          {isLastStep ? (
            <Button
              type="button"
              onClick={submit}
              disabled={!canNext() || submitting}
            >
              {submitting ? "Lancement…" : "Lancer mon analyse"}
              <ArrowRight className="h-4 w-4 ml-1.5" />
            </Button>
          ) : (
            <Button
              type="button"
              onClick={next}
              disabled={!canNext()}
            >
              continuer <ArrowRight className="h-4 w-4 ml-1.5" />
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}

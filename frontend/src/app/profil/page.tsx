"use client"

import { useCallback, useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { Controller, useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { ArrowRight, Check, FileText, ShieldCheck, UploadCloud } from "lucide-react"

import { AppBar } from "@/components/layout/AppBar"
import { ConditionsMatrix } from "@/components/profil/ConditionsMatrix"
import { LiveSynthesis } from "@/components/profil/LiveSynthesis"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { SectionCard } from "@/components/ui/section-card"
import { Skeleton } from "@/components/ui/skeleton"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { api, ApiError } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { cn } from "@/lib/utils"
import type { ConditionsValue } from "@/types/conditions"

/* ── Option sets. Values mirror backend/app/models/profile.py. ───────────── */

const RAYONS = [
  { value: "ma_ville", label: "Ma ville" },
  { value: "30km", label: "Jusqu'à 30 km" },
  { value: "ma_region", label: "Ma région" },
  { value: "toute_la_france", label: "Toute la France" },
]

const TRANCHES_AGE = [
  { value: "moins_25", label: "Moins de 25 ans" },
  { value: "25_34", label: "25 – 34 ans" },
  { value: "35_44", label: "35 – 44 ans" },
  { value: "45_54", label: "45 – 54 ans" },
  { value: "55_plus", label: "55 ans et plus" },
]

// Mobility used to be a separate chip field; the PM merged it in here because
// the two were asking the same question twice.
const SITUATIONS = [
  { value: "en_recherche", label: "En recherche d'emploi" },
  { value: "en_reconversion", label: "En reconversion" },
  { value: "en_poste_evolution", label: "En poste, je souhaite évoluer" },
  { value: "premiere_insertion", label: "Première insertion" },
  { value: "reprise_apres_pause", label: "En reprise après une pause" },
]

const RECONVERSION_SCOPES = [
  { value: "meme_domaine", label: "Rester dans mon domaine" },
  { value: "changer_de_metier", label: "Changer de métier" },
  { value: "changer_de_secteur", label: "Changer de secteur" },
]

const schema = z.object({
  prenom: z.string().min(1, "Prénom requis."),
  nom: z.string().min(1, "Nom requis."),
  ville: z.string().min(1, "Ville requise."),
  rayon: z.string().min(1, "Rayon de recherche requis."),
  tranche_age: z.string().min(1, "Tranche d'âge requise."),
  situation: z.string().min(1, "Situation requise."),
  reconversion_scope: z.string().optional(),
  projet: z.string(),
  projet_document: z.string(),
  contraintes_pratiques: z.string(),
  oeth: z.boolean(),
  consent: z.boolean().refine((v) => v === true, "Le consentement est requis."),
})
type Fields = z.infer<typeof schema>

export default function ProfilPage() {
  const router = useRouter()
  const { user, loading: authLoading } = useAuth()
  const [conditions, setConditions] = useState<ConditionsValue>({})
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const [docState, setDocState] = useState<"idle" | "uploading" | "done" | "error">("idle")
  const [docName, setDocName] = useState("")

  const { register, handleSubmit, control, setValue, watch, reset, formState: { errors } } =
    useForm<Fields>({
      resolver: zodResolver(schema),
      defaultValues: {
        prenom: "", nom: "", ville: "", rayon: "", tranche_age: "",
        situation: "", reconversion_scope: "",
        projet: "", projet_document: "", contraintes_pratiques: "",
        oeth: false, consent: false,
      },
    })

  const situation = watch("situation")
  const consent = watch("consent")

  // The proxy already gates /profil on cookie *presence*, which misses an
  // expired or invalid token. Without this, that case renders the whole form
  // and only fails at submit — losing six blocks of answers, including bloc 5
  // and the OETH box.
  useEffect(() => {
    if (!authLoading && !user) router.replace("/connexion?redirect=/profil")
  }, [authLoading, user, router])

  // Load an existing profile. Bloc 5 comes from its own endpoint — it must
  // never ride on the ordinary profile payload.
  useEffect(() => {
    Promise.all([
      api.get<{ profile: Record<string, string | null> | null }>("/profile", { skipRedirect: true }),
      api.get<{ conditions: ConditionsValue; oeth: boolean }>("/profile/conditions", { skipRedirect: true }),
    ])
      .then(([p, c]) => {
        if (p?.profile) {
          const v = p.profile
          reset({
            prenom: v.prenom ?? "", nom: v.nom ?? "", ville: v.ville ?? "",
            rayon: v.rayon ?? "", tranche_age: v.tranche_age ?? "",
            situation: v.situation ?? "", reconversion_scope: v.reconversion_scope ?? "",
            projet: v.projet ?? "", projet_document: v.projet_document ?? "",
            contraintes_pratiques: v.contraintes_pratiques ?? "",
            // Travels only on the sensitive endpoint, never on this payload.
            oeth: Boolean(c?.oeth),
            consent: Boolean(v.consent_at),
          })
        }
        if (c?.conditions) setConditions(c.conditions)
      })
      .catch(() => { /* no profile yet — start blank */ })
      .finally(() => setLoaded(true))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleDoc = useCallback(async (file: File) => {
    if (file.type !== "application/pdf") { setDocState("error"); return }
    setDocState("uploading")
    const fd = new FormData()
    fd.append("file", file)
    try {
      const res = await api.upload<{ projet_text: string }>("/upload/projet", fd)
      setValue("projet_document", res.projet_text, { shouldValidate: true })
      setDocName(file.name)
      setDocState("done")
    } catch {
      setDocState("error")
    }
  }, [setValue])

  const onSubmit = async (data: Fields) => {
    setSaveError(null)
    setSaving(true)
    try {
      await api.put("/profile", { ...data, conditions })
      router.push("/analyse/nouveau")
    } catch (e) {
      setSaveError(e instanceof ApiError ? e.message : "Erreur inattendue.")
      setSaving(false)
    }
  }

  const err = (k: keyof Fields) =>
    errors[k] && <p className="mt-1 text-[10px] text-destructive">{errors[k]?.message as string}</p>

  // Render nothing while auth resolves — a flash of empty form invites someone
  // to start typing into something that is about to redirect.
  if (authLoading || !user) {
    return (
      <div className="min-h-screen bg-secondary">
        <AppBar />
        <div className="mx-auto max-w-3xl px-4 py-8">
          <Skeleton className="h-9 w-64" />
          <div className="mt-6 space-y-5">
            {[0, 1, 2].map((i) => <Skeleton key={i} className="h-44 rounded-2xl" />)}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-secondary">
      <AppBar />
      <div className="mx-auto max-w-3xl px-4 py-8">
        <div className="mb-6">
          <p className="eyebrow text-orange-dark">Profil de base</p>
          <h1 className="mt-1 font-display text-2xl font-bold text-navy sm:text-3xl">
            On commence par vous
          </h1>
          <p className="mt-1.5 text-sm text-muted-foreground">
            Rempli une fois. Aucune de ces questions ne vous sera reposée : votre analyse et
            votre parcours s&apos;appuient dessus.
          </p>
        </div>

        {saveError && (
          <Alert variant="destructive" className="mb-4">
            <AlertDescription>{saveError}</AlertDescription>
          </Alert>
        )}

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
          {/* ── Bloc 1 ─────────────────────────────────────────────────── */}
          <SectionCard n={1} title="Vous">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <Label htmlFor="prenom">Prénom</Label>
                <Input id="prenom" className="mt-1.5" {...register("prenom")} />
                {err("prenom")}
              </div>
              <div>
                <Label htmlFor="nom">Nom</Label>
                <Input
                  id="nom"
                  className="mt-1.5 uppercase"
                  {...register("nom", {
                    onChange: (e) => setValue("nom", e.target.value.toUpperCase()),
                  })}
                />
                {err("nom")}
              </div>
              <div>
                <Label htmlFor="ville">Votre ville</Label>
                <Input id="ville" className="mt-1.5" {...register("ville")} />
                {err("ville")}
              </div>
              <div>
                <Label>Rayon de recherche</Label>
                <Controller
                  name="rayon"
                  control={control}
                  render={({ field }) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger className="mt-1.5 w-full"><SelectValue placeholder="Choisir…" /></SelectTrigger>
                      <SelectContent>
                        {RAYONS.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  )}
                />
                {err("rayon")}
              </div>
              <div>
                <Label>Tranche d&apos;âge</Label>
                <Controller
                  name="tranche_age"
                  control={control}
                  render={({ field }) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger className="mt-1.5 w-full"><SelectValue placeholder="Choisir…" /></SelectTrigger>
                      <SelectContent>
                        {TRANCHES_AGE.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  )}
                />
                {err("tranche_age")}
              </div>
            </div>
          </SectionCard>

          {/* ── Bloc 2 ─────────────────────────────────────────────────── */}
          <SectionCard n={2} title="Votre situation" hint="Où en êtes-vous aujourd'hui ? Une seule réponse.">
            <Controller
              name="situation"
              control={control}
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger className="w-full"><SelectValue placeholder="Choisir…" /></SelectTrigger>
                  <SelectContent>
                    {SITUATIONS.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              )}
            />
            {err("situation")}

            {situation === "en_reconversion" && (
              <div className="mt-4 rounded-lg bg-secondary/70 p-3">
                <Label>Quel changement visez-vous ?</Label>
                <Controller
                  name="reconversion_scope"
                  control={control}
                  render={({ field }) => (
                    <Select value={field.value ?? ""} onValueChange={field.onChange}>
                      <SelectTrigger className="mt-1.5 w-full"><SelectValue placeholder="Choisir…" /></SelectTrigger>
                      <SelectContent>
                        {RECONVERSION_SCOPES.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  )}
                />
              </div>
            )}
          </SectionCard>

          {/* ── Bloc 3 ─────────────────────────────────────────────────── */}
          <SectionCard
            n={3}
            title="Votre projet"
            hint="Secteur, type de poste, ce que vous voulez retrouver au quotidien. Si vous ne savez pas encore, dites-le : le parcours est fait pour ça."
          >
            <Textarea rows={4} placeholder="Décrivez votre projet, ou ce qui compte pour vous dans un travail…" {...register("projet")} />

            <div className="mt-4">
              <p className="mb-2 text-xs font-medium text-navy">
                Vous avez une cible précise ? Ajoutez une offre d&apos;emploi, une fiche de poste
                ou une fiche métier.
              </p>
              <div
                onClick={() => document.getElementById("projet-doc")?.click()}
                onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) handleDoc(f) }}
                onDragOver={(e) => e.preventDefault()}
                className={cn(
                  "flex cursor-pointer items-center gap-3 rounded-xl border border-dashed border-input p-4 transition-colors hover:border-orange/50",
                  docState === "done" && "border-success/40 bg-success/5",
                  docState === "error" && "border-destructive/40",
                )}
              >
                {docState === "done"
                  ? <FileText className="size-4 shrink-0 text-success" />
                  : <UploadCloud className="size-4 shrink-0 text-muted-foreground" />}
                <span className="text-xs text-muted-foreground">
                  {docState === "uploading" && "Lecture du document…"}
                  {docState === "done" && `${docName} — le rapport comparera votre profil à ses exigences, point par point.`}
                  {docState === "error" && "PDF illisible. Réessayez avec un autre fichier."}
                  {docState === "idle" && "Glissez un PDF ici, ou cliquez pour choisir (10 Mo max)."}
                </span>
                <input id="projet-doc" type="file" accept="application/pdf" className="hidden"
                       onChange={(e) => { const f = e.target.files?.[0]; if (f) handleDoc(f) }} />
              </div>
            </div>
          </SectionCard>

          {/* ── Bloc 4 ─────────────────────────────────────────────────── */}
          <SectionCard
            n={4}
            title="Vos contraintes pratiques"
            hint="Horaires, transport, disponibilité, salaire minimum, temps partiel."
          >
            <Textarea rows={3} placeholder="Y a-t-il des contraintes à prendre en compte ?" {...register("contraintes_pratiques")} />
            {/* CDC §3.1 — this warning is part of the field, not decoration.
                It is what keeps health data out of a free-text box. */}
            <div className="mt-3 rounded-lg bg-[#FFF3CD] px-3 py-2.5 text-xs leading-relaxed text-[#7A4A00]">
              N&apos;indiquez aucune information de santé, aucun diagnostic, aucun traitement.
              Si une situation personnelle a un effet sur votre travail, décrivez seulement cet
              effet : « je ne suis pas disponible avant 9h », « j&apos;ai besoin d&apos;un poste
              sans conduite ».
            </div>
          </SectionCard>

          {/* ── Bloc 5 ─────────────────────────────────────────────────── */}
          <SectionCard
            n={5}
            title="Vos conditions de travail"
            hint={
              <>
                Les mêmes questions pour tout le monde. On ne demande jamais la cause d&apos;une
                limitation, seulement son effet sur le travail. <span className="font-medium">Facultatif</span> —
                mais c&apos;est ce qui rend le rapport précis.
              </>
            }
          >
            <ConditionsMatrix value={conditions} onChange={setConditions} />
            <div className="mt-4">
              <LiveSynthesis value={conditions} />
            </div>
          </SectionCard>

          {/* ── Bloc 6 ─────────────────────────────────────────────────── */}
          <SectionCard n={6} title="Vos droits et votre accord">
            {/* The OETH box must trigger nothing visible: no new field, no
                re-layout, no extra request. The effect appears only in the
                generated report. Nothing here may react to it. */}
            <label className="flex cursor-pointer items-start gap-3 rounded-lg bg-secondary/60 p-3">
              <Controller
                name="oeth"
                control={control}
                render={({ field }) => (
                  <Checkbox className="mt-0.5" checked={field.value} onCheckedChange={field.onChange} />
                )}
              />
              <span className="text-xs leading-relaxed text-navy-700">
                Je suis bénéficiaire de l&apos;obligation d&apos;emploi des travailleurs
                handicapés (OETH).
                <span className="mt-1 block text-muted-foreground">
                  L&apos;OETH est un statut administratif qui ouvre des droits — accompagnement
                  Cap Emploi, financement d&apos;aménagements par l&apos;Agefiph. Cette
                  information est stockée séparément et chiffrée. Elle n&apos;apparaît jamais
                  dans votre rapport ni dans les documents que vous partagez.
                </span>
              </span>
            </label>

            <label className="mt-3 flex cursor-pointer items-start gap-3 rounded-lg bg-secondary/60 p-3 has-[:checked]:bg-peach-soft/60">
              <Controller
                name="consent"
                control={control}
                render={({ field }) => (
                  <Checkbox className="mt-0.5" checked={field.value} onCheckedChange={field.onChange} />
                )}
              />
              <span className="text-xs leading-relaxed text-navy-700">
                J&apos;accepte que mes données soient traitées pour produire mon analyse et
                mon accompagnement. Je peux les consulter, les corriger et les supprimer à tout
                moment depuis mon espace.
              </span>
            </label>
            {err("consent")}
          </SectionCard>

          <div className="flex flex-col items-start justify-between gap-3 rounded-2xl bg-card p-5 ring-1 ring-foreground/10 sm:flex-row sm:items-center">
            <p className="flex items-center gap-2 text-xs text-muted-foreground">
              <ShieldCheck className="size-3.5 shrink-0 text-success" />
              Données chiffrées, supprimables à tout moment.
            </p>
            {/* CDC §3.1: the button stays inactive until consent is ticked. */}
            <Button type="submit" size="lg" disabled={!consent || saving || !loaded}>
              {saving ? "Enregistrement…" : "Enregistrer et continuer"}
              {saving ? <Check className="size-4" /> : <ArrowRight className="size-4" />}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}

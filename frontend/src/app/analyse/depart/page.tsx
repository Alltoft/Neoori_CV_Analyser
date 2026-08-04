"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { ArrowRight } from "lucide-react"

import { AppBar } from "@/components/layout/AppBar"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { SectionCard } from "@/components/ui/section-card"
import { Textarea } from "@/components/ui/textarea"
import { api, ApiError } from "@/lib/api"
import type { Analysis } from "@/types"

/**
 * Parcours 3 — « Je pars de zéro ». No CV required.
 *
 * The minimum lengths are deliberately short. This parcours exists for people
 * who don't have a CV, and a long-answer requirement is exactly the barrier it
 * is meant to remove — the backend uses the same lower threshold.
 */
const QUESTIONS = [
  {
    name: "experiences" as const,
    label: "Qu'avez-vous fait jusqu'à présent ?",
    hint: "Listez tout : jobs, petits boulots, bénévolat, sport, garde d'un proche, projets personnels. Rien n'est trop petit.",
    rows: 5,
  },
  {
    name: "aime_faire" as const,
    label: "Qu'est-ce que vous aimez faire, ou êtes à l'aise pour faire, même sans avoir été payé ?",
    hint: "Organiser, convaincre, réparer, enseigner, prendre soin, construire…",
    rows: 4,
  },
  {
    name: "refus" as const,
    label: "Y a-t-il des choses que vous ne voulez pas ou ne pouvez pas faire ?",
    hint: "Travail de nuit, port de charges, contact client, déplacements…",
    rows: 3,
  },
  {
    name: "contraintes" as const,
    label: "Avez-vous des contraintes pratiques pour travailler ?",
    hint: "Zone, horaires, transport.",
    rows: 3,
  },
  {
    name: "bon_travail" as const,
    label: "Qu'est-ce qu'un « bon travail » pour vous ?",
    hint: "Décrivez une journée, une ambiance, ce que vous voudriez ressentir — sans nommer un métier.",
    rows: 4,
  },
]

const MIN = 10
const short = "Quelques mots de plus, pour qu'on puisse s'appuyer dessus."

const schema = z.object({
  experiences: z.string().min(MIN, short),
  aime_faire: z.string().min(MIN, short),
  refus: z.string().min(MIN, short),
  contraintes: z.string().min(MIN, short),
  bon_travail: z.string().min(MIN, short),
})
type Fields = z.infer<typeof schema>

export default function DepartPage() {
  const router = useRouter()
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const { register, handleSubmit, formState: { errors } } = useForm<Fields>({
    resolver: zodResolver(schema),
    defaultValues: { experiences: "", aime_faire: "", refus: "", contraintes: "", bon_travail: "" },
  })

  const onSubmit = async (data: Fields) => {
    setSubmitError(null)
    setSubmitting(true)
    try {
      const res = await api.post<{ analysis: Analysis }>("/analyses/", {
        inputs: { ...data, _path: "3" },
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
      <div className="bg-teal h-1.5 w-full" role="presentation" aria-hidden />
      <div className="mx-auto max-w-2xl px-4 py-8">
        <div className="mb-6">
          <p className="eyebrow text-orange-dark">Parcours 3</p>
          <h1 className="mt-1 font-display text-2xl font-bold text-navy sm:text-3xl">
            Je pars de zéro
          </h1>
          <p className="mt-1.5 text-sm text-muted-foreground">
            Cinq questions, pas de CV. Ce que vous avez fait en dehors d&apos;un emploi compte
            autant — c&apos;est de la matière première.
          </p>
        </div>

        {submitError && (
          <Alert variant="destructive" className="mb-4">
            <AlertDescription>{submitError}</AlertDescription>
          </Alert>
        )}

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
          {QUESTIONS.map((q, i) => (
            <SectionCard key={q.name} n={i + 1} title={q.label} hint={q.hint}>
              <Textarea rows={q.rows} {...register(q.name)} />
              {errors[q.name] && (
                <p className="mt-1 text-[10px] text-destructive">{errors[q.name]?.message}</p>
              )}
            </SectionCard>
          ))}

          <div className="flex flex-col items-start justify-between gap-3 rounded-2xl bg-card p-5 ring-1 ring-foreground/10 sm:flex-row sm:items-center">
            <p className="text-xs text-muted-foreground">
              Vous avez un début de CV ?{" "}
              <Link href="/profil" className="link-underline text-navy">Ajoutez-le au profil</Link>
              {" "}— il sera pris en compte.
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

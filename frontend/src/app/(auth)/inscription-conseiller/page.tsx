"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { useAuth } from "@/lib/auth"
import { ApiError } from "@/lib/api"
import { counselor } from "@/lib/counselor"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { AuthLayout } from "@/components/layout/AuthLayout"

// The approval file: what the admin decides on. Declared information only —
// no document upload, so a refusal costs the person nothing but the form.
const schema = z
  .object({
    structure: z.string().min(1, "Structure requise."),
    fonction: z.string().min(1, "Fonction requise."),
    telephone: z.string().min(6, "Téléphone requis."),
    email_pro: z.string().email("Email professionnel invalide.").or(z.literal("")),
    message: z.string(),
    email: z.string().email("Email invalide."),
    password: z.string().min(8, "8 caractères minimum."),
    confirm: z.string(),
    consent: z.boolean().refine((v) => v === true, {
      message: "Veuillez accepter les CGV et la politique de confidentialité.",
    }),
  })
  .refine((d) => d.password === d.confirm, {
    message: "Les mots de passe ne correspondent pas.",
    path: ["confirm"],
  })
type Fields = z.infer<typeof schema>

export default function InscriptionConseillerPage() {
  const { refresh } = useAuth()
  const router = useRouter()
  const [error, setError] = useState<string | null>(null)

  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<Fields>({
    resolver: zodResolver(schema),
    defaultValues: { consent: false, message: "", email_pro: "" },
  })

  const onSubmit = async (values: Fields) => {
    setError(null)
    try {
      await counselor.apply({
        structure: values.structure,
        fonction: values.fonction,
        telephone: values.telephone,
        email_pro: values.email_pro || undefined,
        message: values.message || undefined,
        email: values.email,
        password: values.password,
        consent: values.consent,
      })
      // apply() sets the cookies; refresh() puts the user in context before the
      // /conseiller page reads it.
      await refresh()
      router.push("/conseiller")
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erreur lors de l'envoi de la demande.")
    }
  }

  return (
    <AuthLayout>
      <h1 className="font-display text-2xl font-bold text-navy">Compte conseiller</h1>
      <p className="mt-1.5 text-sm text-muted-foreground">
        Votre demande est examinée avant l&apos;ouverture du compte.
      </p>

      <form onSubmit={handleSubmit(onSubmit)} className="mt-7 space-y-4">
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className="space-y-1.5">
          <Label htmlFor="structure">Structure</Label>
          <Input id="structure" className="h-10" placeholder="Cap Emploi 31" {...register("structure")} />
          {errors.structure && <p className="text-xs text-destructive">{errors.structure.message}</p>}
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="fonction">Fonction</Label>
            <Input id="fonction" className="h-10" placeholder="Conseillère en insertion" {...register("fonction")} />
            {errors.fonction && <p className="text-xs text-destructive">{errors.fonction.message}</p>}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="telephone">Téléphone</Label>
            <Input id="telephone" type="tel" autoComplete="tel" className="h-10" placeholder="05 61 00 00 00" {...register("telephone")} />
            {errors.telephone && <p className="text-xs text-destructive">{errors.telephone.message}</p>}
          </div>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="email_pro">Email professionnel (facultatif)</Label>
          <Input id="email_pro" type="email" className="h-10" placeholder="c.martin@capemploi.fr" {...register("email_pro")} />
          {errors.email_pro && <p className="text-xs text-destructive">{errors.email_pro.message}</p>}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="message">Précisions (facultatif)</Label>
          <Textarea id="message" rows={3} placeholder="Nombre de personnes accompagnées, contexte…" {...register("message")} />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="email">Email de connexion</Label>
          <Input id="email" type="email" autoComplete="email" className="h-10" placeholder="vous@exemple.fr" {...register("email")} />
          {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="password">Mot de passe</Label>
            <Input id="password" type="password" autoComplete="new-password" className="h-10" placeholder="8 caractères minimum" {...register("password")} />
            {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="confirm">Confirmer</Label>
            <Input id="confirm" type="password" autoComplete="new-password" className="h-10" placeholder="••••••••" {...register("confirm")} />
            {errors.confirm && <p className="text-xs text-destructive">{errors.confirm.message}</p>}
          </div>
        </div>

        <div className="space-y-1.5">
          <label className="flex items-start gap-2.5 text-xs leading-relaxed text-muted-foreground">
            <input
              type="checkbox"
              className="mt-0.5 size-4 shrink-0 rounded border-input accent-[var(--primary)]"
              {...register("consent")}
            />
            <span>
              J&apos;accepte les{" "}
              <Link href="/cgv" target="_blank" className="text-navy underline underline-offset-2">CGV</Link>{" "}
              et la{" "}
              <Link href="/confidentialite" target="_blank" className="text-navy underline underline-offset-2">politique de confidentialité</Link>.
            </span>
          </label>
          {errors.consent && <p className="text-xs text-destructive">{errors.consent.message}</p>}
        </div>

        <Button type="submit" size="lg" className="h-11 w-full" disabled={isSubmitting}>
          {isSubmitting ? "Envoi…" : "Envoyer ma demande"}
        </Button>
      </form>

      <p className="mt-5 text-center text-sm text-muted-foreground">
        Vous cherchez un compte candidat ?{" "}
        <Link href="/inscription" className="link-underline font-medium text-orange-dark">
          Créer un compte
        </Link>
      </p>
    </AuthLayout>
  )
}

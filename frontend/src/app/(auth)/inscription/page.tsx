"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { useAuth } from "@/lib/auth"
import { ApiError } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { AuthLayout } from "@/components/layout/AuthLayout"

const schema = z
  .object({
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

export default function InscriptionPage() {
  const { register: registerUser } = useAuth()
  const router = useRouter()
  const [error, setError] = useState<string | null>(null)

  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<Fields>({
    resolver: zodResolver(schema),
    defaultValues: { consent: false },
  })

  const onSubmit = async ({ email, password }: Fields) => {
    setError(null)
    try {
      await registerUser(email, password)
      router.push("/espace")
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erreur lors de la création du compte.")
    }
  }

  return (
    <AuthLayout>
      <h1 className="font-display text-2xl font-bold text-navy">Créer un compte</h1>
      <p className="mt-1.5 text-sm text-muted-foreground">Gratuit · 1 analyse offerte.</p>

      <form onSubmit={handleSubmit(onSubmit)} className="mt-7 space-y-4">
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className="space-y-1.5">
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" autoComplete="email" className="h-10" placeholder="vous@exemple.fr" {...register("email")} />
          {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="password">Mot de passe</Label>
          <Input id="password" type="password" autoComplete="new-password" className="h-10" placeholder="8 caractères minimum" {...register("password")} />
          {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="confirm">Confirmer le mot de passe</Label>
          <Input id="confirm" type="password" autoComplete="new-password" className="h-10" placeholder="••••••••" {...register("confirm")} />
          {errors.confirm && <p className="text-xs text-destructive">{errors.confirm.message}</p>}
        </div>

        <div className="space-y-1.5">
          <label className="flex items-start gap-2.5 text-xs leading-relaxed text-muted-foreground">
            <input
              type="checkbox"
              className="mt-0.5 size-4 shrink-0 rounded border-input accent-[var(--primary)]"
              {...register("consent")}
            />
            <span>
              J’accepte les{" "}
              <Link href="/cgv" target="_blank" className="text-navy underline underline-offset-2">CGV</Link>{" "}
              et la{" "}
              <Link href="/confidentialite" target="_blank" className="text-navy underline underline-offset-2">politique de confidentialité</Link>.
            </span>
          </label>
          {errors.consent && <p className="text-xs text-destructive">{errors.consent.message}</p>}
        </div>

        <Button type="submit" size="lg" className="h-11 w-full" disabled={isSubmitting}>
          {isSubmitting ? "Création…" : "Créer mon compte"}
        </Button>
      </form>

      <p className="mt-5 text-center text-sm text-muted-foreground">
        Déjà un compte ?{" "}
        <Link href="/connexion" className="link-underline font-medium text-orange-dark">
          Se connecter
        </Link>
      </p>
    </AuthLayout>
  )
}

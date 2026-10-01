"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { Controller, useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Eye, EyeOff } from "lucide-react"
import { useAuth } from "@/lib/auth"
import { ApiError } from "@/lib/api"
import { counselor } from "@/lib/counselor"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { AuthLayout } from "@/components/layout/AuthLayout"
import { VerificationPending } from "@/components/auth/VerificationPending"
import type { DomaineActivite, TypeStructure } from "@/types"

// Option lists for this form only. Slugs mirror `TypeStructure` /
// `DomaineActivite` in @/types; the French wording lives here, beside the
// fields that render it, same as the rest of the app's option lists.
const TYPES_STRUCTURE: { value: TypeStructure; label: string }[] = [
  { value: "cap_emploi", label: "Cap Emploi / OPS" },
  { value: "mission_locale", label: "Mission locale" },
  { value: "france_travail", label: "France Travail" },
  { value: "association", label: "Association" },
  { value: "esat_ea", label: "ESAT / Entreprise adaptée" },
  { value: "formation_cfa", label: "Organisme de formation / CFA" },
  { value: "etablissement_scolaire", label: "Établissement scolaire ou universitaire" },
  { value: "collectivite", label: "Collectivité / service public" },
  { value: "medico_social", label: "Structure médico-sociale ou de santé" },
  { value: "entreprise_rh", label: "Entreprise / cabinet RH, recrutement, intérim" },
  { value: "organisation_pro", label: "Organisation professionnelle / OPCO / syndicat" },
  { value: "independant", label: "Indépendant / auto-entrepreneur / consultant" },
  { value: "autre", label: "Autre" },
]

const DOMAINES: { value: DomaineActivite; label: string }[] = [
  { value: "insertion_emploi", label: "Insertion / emploi" },
  { value: "handicap", label: "Handicap" },
  { value: "orientation_bilan", label: "Orientation / bilan de compétences" },
  { value: "formation", label: "Formation" },
  { value: "recrutement_entreprises", label: "Recrutement / relations entreprises" },
  { value: "accompagnement_social", label: "Accompagnement social / médico-social" },
  { value: "education", label: "Éducation" },
  { value: "autre", label: "Autre" },
]

// Shape of the BAN (Base Adresse Nationale) search response, trimmed to the
// fields this form reads. https://api-adresse.data.gouv.fr
interface BanFeature {
  properties?: {
    label?: string
    name?: string
    postcode?: string
    city?: string
  }
}
interface BanResponse {
  features?: BanFeature[]
}

// The approval file: what the admin decides on. Declared information only —
// no document upload, so a refusal costs the person nothing but the form.
const schema = z
  .object({
    structure: z.string().min(1, "Nom de la structure requis."),
    type_structure: z.string().min(1, "Type de structure requis."),
    type_structure_autre: z.string(),
    siret: z.string(),
    adresse_rue: z.string().min(1, "Rue requise."),
    adresse_code_postal: z.string().min(1, "Code postal requis."),
    adresse_ville: z.string().min(1, "Ville requise."),
    domaines: z.array(z.string()).min(1, "Sélectionnez au moins un domaine."),
    nom_complet: z.string().min(1, "Prénom et nom requis."),
    fonction: z.string().min(1, "Fonction requise."),
    telephone: z.string().min(1, "Téléphone requis."),
    email: z.string().email("Email invalide."),
    password: z.string().min(8, "8 caractères minimum."),
    confirm: z.string(),
    consent: z.boolean().refine((v) => v === true, {
      message: "Veuillez accepter les CGV.",
    }),
    consent_donnees: z.boolean().refine((v) => v === true, {
      message: "Veuillez consentir au traitement de vos données.",
    }),
  })
  .refine((d) => d.password === d.confirm, {
    message: "Les mots de passe ne correspondent pas.",
    path: ["confirm"],
  })
  .refine((d) => d.type_structure !== "autre" || d.type_structure_autre.trim().length > 0, {
    message: "Précisez le type de structure.",
    path: ["type_structure_autre"],
  })
  .refine((d) => d.type_structure === "independant" || d.siret.replace(/\s+/g, "").length > 0, {
    message: "SIRET requis.",
    path: ["siret"],
  })
  .refine((d) => {
    const digits = d.siret.replace(/\s+/g, "")
    return digits.length === 0 || /^\d{14}$/.test(digits)
  }, {
    message: "Le SIRET doit comporter 14 chiffres.",
    path: ["siret"],
  })
type Fields = z.infer<typeof schema>

export default function InscriptionConseillerPage() {
  const { user, loading, refresh } = useAuth()
  const router = useRouter()
  const [error, setError] = useState<string | null>(null)
  const [submitted, setSubmitted] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  // Set when the demande created a new account: it opens once its address is
  // confirmed, so the person is sent to their inbox, not to /conseiller.
  const [pending, setPending] = useState<{ email: string; mailSent: boolean } | null>(null)

  // Someone who already has a demande is sent to their status page instead of
  // this form. A pending conseiller keeps role="candidate" until approval, so
  // the AppBar's « Espace conseiller » entry does not show for them — this link
  // is their only way back, and letting them re-submit would only earn a 409.
  useEffect(() => {
    if (loading || !user) return
    counselor.me()
      .then((r) => { if (r.profile) router.replace("/conseiller") })
      .catch(() => { /* No demande, or unreachable: leave them on the form. */ })
  }, [loading, user, router])

  const { register, control, handleSubmit, setValue, watch, reset, formState: { errors, isSubmitting } } =
    useForm<Fields>({
      resolver: zodResolver(schema),
      defaultValues: {
        structure: "", type_structure: "", type_structure_autre: "", siret: "",
        adresse_rue: "", adresse_code_postal: "", adresse_ville: "", domaines: [],
        nom_complet: "", fonction: "", telephone: "",
        email: "", password: "", confirm: "",
        consent: false, consent_donnees: false,
      },
    })

  const typeStructure = watch("type_structure")
  const domaines = watch("domaines")

  // Address autocomplete — Base Adresse Nationale. Debounced at ~300ms, fired
  // only once 3+ characters are typed. Never a gate: the three fields stay
  // plain registered inputs the person can always type by hand, and a failed
  // or empty lookup just leaves the picklist empty.
  const [rueQuery, setRueQuery] = useState("")
  const [suggestions, setSuggestions] = useState<BanFeature[]>([])
  const [suggestionsOpen, setSuggestionsOpen] = useState(false)

  useEffect(() => {
    if (rueQuery.trim().length < 3) {
      setSuggestions([])
      return
    }
    const controller = new AbortController()
    const timer = setTimeout(() => {
      fetch(`https://api-adresse.data.gouv.fr/search/?q=${encodeURIComponent(rueQuery)}&limit=5`, {
        signal: controller.signal,
      })
        .then((res) => (res.ok ? (res.json() as Promise<BanResponse>) : null))
        .then((data) => {
          if (!data) return
          setSuggestions(Array.isArray(data.features) ? data.features : [])
          setSuggestionsOpen(true)
        })
        .catch(() => {
          // API down, slow, or the request was aborted by the next keystroke:
          // fail silently, manual entry always still works.
          setSuggestions([])
        })
    }, 300)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [rueQuery])

  const { onChange: rueOnChange, ...rueField } = register("adresse_rue")

  const pickSuggestion = (f: BanFeature) => {
    const p = f.properties ?? {}
    const rue = p.name ?? p.label ?? ""
    setValue("adresse_rue", rue, { shouldValidate: true, shouldDirty: true })
    setValue("adresse_code_postal", p.postcode ?? "", { shouldValidate: true, shouldDirty: true })
    setValue("adresse_ville", p.city ?? "", { shouldValidate: true, shouldDirty: true })
    // rueQuery only drives the search effect, not the visible field (setValue
    // above already updates that) — leaving it alone stops the pick from
    // re-triggering a fresh lookup and reopening the picklist on itself.
    setSuggestions([])
    setSuggestionsOpen(false)
  }

  const toggleDomaine = (value: DomaineActivite, checked: boolean) => {
    const current = domaines ?? []
    setValue(
      "domaines",
      checked ? [...current, value] : current.filter((d) => d !== value),
      { shouldValidate: true, shouldDirty: true },
    )
  }

  const onSubmit = async (values: Fields) => {
    setError(null)
    try {
      const res = await counselor.apply({
        structure: values.structure,
        type_structure: values.type_structure as TypeStructure,
        type_structure_autre: values.type_structure === "autre" ? values.type_structure_autre : undefined,
        siret: values.siret ? values.siret.replace(/\s+/g, "") : undefined,
        adresse_rue: values.adresse_rue,
        adresse_code_postal: values.adresse_code_postal,
        adresse_ville: values.adresse_ville,
        domaines: values.domaines as DomaineActivite[],
        nom_complet: values.nom_complet,
        fonction: values.fonction,
        telephone: values.telephone,
        consent: values.consent,
        consent_donnees: values.consent_donnees,
        email: values.email,
        password: values.password,
      })
      // The server's answer decides, not the client's idea of who is signed in:
      // mail_sent comes back only when this call created the account, and a
      // lapsed session would make `!user` disagree with it. That account has no
      // session and opens once its address is confirmed; the link lands on
      // /conseiller.
      if (res.mail_sent !== undefined) {
        setPending({ email: values.email, mailSent: res.mail_sent })
        return
      }
      // A signed-in candidate keeps their session; refresh() puts the demande's
      // user in context before the /conseiller page reads it. The panel below
      // shows for a moment first so the 48h-delay message cannot be missed.
      await refresh()
      setSubmitted(true)
      setTimeout(() => router.push("/conseiller"), 3000)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erreur lors de l'envoi de la demande.")
    }
  }

  // Back to a blank form: the first address was the wrong one, and keeping the
  // rest of the answers would keep the password in memory for nothing.
  const restart = () => {
    reset()
    setRueQuery("")
    setSuggestions([])
    setSuggestionsOpen(false)
    setShowPassword(false)
    setError(null)
    setPending(null)
  }

  if (pending) {
    return (
      <AuthLayout>
        {/* Keyed by address: the countdown and the failure flag start from the
            props once, so a second demande must never inherit the first's. */}
        <VerificationPending
          key={pending.email}
          email={pending.email}
          next="/conseiller"
          mailSent={pending.mailSent}
          onRestart={restart}
        />
        <p className="mt-6 text-sm text-muted-foreground">
          Votre demande est enregistrée. Elle sera examinée dès votre adresse confirmée, sous 48 h ouvrées.
        </p>
      </AuthLayout>
    )
  }

  if (submitted) {
    return (
      <AuthLayout>
        <h1 className="font-display text-2xl font-bold text-navy">Demande envoyée</h1>
        <Alert className="mt-6">
          <AlertDescription className="text-sm text-foreground">
            Merci, votre demande est bien reçue. Nous l&apos;examinons et vous répondons sous 48 h ouvrées.
          </AlertDescription>
        </Alert>
        <p className="mt-5 text-center text-sm text-muted-foreground">Redirection en cours…</p>
      </AuthLayout>
    )
  }

  return (
    <AuthLayout>
      <h1 className="font-display text-2xl font-bold text-navy">Compte conseiller</h1>
      <p className="mt-1.5 text-sm text-muted-foreground">
        Votre demande est examinée avant l&apos;ouverture du compte. Vous recevrez une réponse sous 48 h ouvrées.
      </p>

      <form onSubmit={handleSubmit(onSubmit)} className="mt-7 space-y-6">
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Section 1 — Votre structure */}
        <div className="space-y-4">
          <h2 className="font-display text-base font-semibold text-navy">Votre structure</h2>

          <div className="space-y-1.5">
            <Label htmlFor="structure">Nom de la structure</Label>
            <Input id="structure" className="h-10" placeholder="Cap Emploi 31" {...register("structure")} />
            {errors.structure && <p className="text-xs text-destructive">{errors.structure.message}</p>}
          </div>

          <div className="space-y-1.5">
            <Label>Type de structure</Label>
            <Controller
              name="type_structure"
              control={control}
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger className="h-10 w-full"><SelectValue placeholder="Choisir…" /></SelectTrigger>
                  <SelectContent>
                    {TYPES_STRUCTURE.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              )}
            />
            {errors.type_structure && <p className="text-xs text-destructive">{errors.type_structure.message}</p>}
          </div>

          {typeStructure === "autre" && (
            <div className="space-y-1.5">
              <Label htmlFor="type_structure_autre">Précisez</Label>
              <Input id="type_structure_autre" className="h-10" {...register("type_structure_autre")} />
              {errors.type_structure_autre && (
                <p className="text-xs text-destructive">{errors.type_structure_autre.message}</p>
              )}
            </div>
          )}

          <div className="space-y-1.5">
            <Label htmlFor="siret">
              {typeStructure === "independant" ? "SIRET (facultatif)" : "SIRET"}
            </Label>
            <Input
              id="siret"
              inputMode="numeric"
              className="h-10"
              placeholder="123 456 789 00012"
              {...register("siret")}
            />
            {errors.siret && <p className="text-xs text-destructive">{errors.siret.message}</p>}
          </div>

          <div className="relative space-y-1.5">
            <Label htmlFor="adresse_rue">Rue</Label>
            <Input
              id="adresse_rue"
              className="h-10"
              placeholder="12 rue de la Gare"
              autoComplete="off"
              {...rueField}
              onChange={(e) => {
                rueOnChange(e)
                setRueQuery(e.target.value)
              }}
              onFocus={() => { if (suggestions.length > 0) setSuggestionsOpen(true) }}
              onBlur={() => {
                // Delayed so a click on a suggestion registers before the list unmounts.
                setTimeout(() => setSuggestionsOpen(false), 150)
              }}
            />
            {errors.adresse_rue && <p className="text-xs text-destructive">{errors.adresse_rue.message}</p>}
            {suggestionsOpen && suggestions.length > 0 && (
              <ul className="absolute z-20 mt-1 w-full overflow-hidden rounded-lg border border-input bg-popover text-popover-foreground shadow-md">
                {suggestions.map((f, i) => (
                  <li key={i}>
                    <button
                      type="button"
                      className="block w-full px-2.5 py-1.5 text-left text-sm hover:bg-accent hover:text-accent-foreground"
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => pickSuggestion(f)}
                    >
                      {f.properties?.label}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="adresse_code_postal">Code postal</Label>
              <Input id="adresse_code_postal" className="h-10" placeholder="31000" {...register("adresse_code_postal")} />
              {errors.adresse_code_postal && (
                <p className="text-xs text-destructive">{errors.adresse_code_postal.message}</p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="adresse_ville">Ville</Label>
              <Input id="adresse_ville" className="h-10" placeholder="Toulouse" {...register("adresse_ville")} />
              {errors.adresse_ville && <p className="text-xs text-destructive">{errors.adresse_ville.message}</p>}
            </div>
          </div>

          <div className="space-y-1.5">
            <Label>Domaine d&apos;activité</Label>
            <div className="grid gap-2 sm:grid-cols-2">
              {DOMAINES.map((o) => (
                <label key={o.value} className="flex items-center gap-2.5 text-sm text-foreground">
                  <input
                    type="checkbox"
                    className="size-4 shrink-0 rounded border-input accent-[var(--primary)]"
                    checked={(domaines ?? []).includes(o.value)}
                    onChange={(e) => toggleDomaine(o.value, e.target.checked)}
                  />
                  {o.label}
                </label>
              ))}
            </div>
            {errors.domaines && <p className="text-xs text-destructive">{errors.domaines.message}</p>}
          </div>
        </div>

        {/* Section 2 — Vous */}
        <div className="space-y-4">
          <h2 className="font-display text-base font-semibold text-navy">Vous</h2>

          <div className="space-y-1.5">
            <Label htmlFor="nom_complet">Prénom et nom</Label>
            <Input id="nom_complet" className="h-10" placeholder="Claire Martin" {...register("nom_complet")} />
            {errors.nom_complet && <p className="text-xs text-destructive">{errors.nom_complet.message}</p>}
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
        </div>

        {/* Section 3 — Connexion */}
        <div className="space-y-4">
          <h2 className="font-display text-base font-semibold text-navy">Connexion</h2>

          <div className="space-y-1.5">
            <Label htmlFor="email">Email professionnel</Label>
            <Input id="email" type="email" autoComplete="email" className="h-10" placeholder="vous@exemple.fr" {...register("email")} />
            <p className="text-xs text-muted-foreground">Cet email vous servira à vous connecter.</p>
            {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="password">Mot de passe</Label>
            <div className="relative">
              <Input
                id="password"
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                className="h-10 pr-10"
                placeholder="8 caractères minimum"
                {...register("password")}
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? "Masquer le mot de passe" : "Afficher le mot de passe"}
                className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-muted-foreground hover:text-foreground"
              >
                {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
              </button>
            </div>
            {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="confirm">Confirmation du mot de passe</Label>
            <Input id="confirm" type="password" autoComplete="new-password" className="h-10" placeholder="••••••••" {...register("confirm")} />
            {errors.confirm && <p className="text-xs text-destructive">{errors.confirm.message}</p>}
          </div>
        </div>

        {/* Section 4 — Validation */}
        <div className="space-y-3">
          <h2 className="font-display text-base font-semibold text-navy">Validation</h2>

          <div className="space-y-1.5">
            <label className="flex items-start gap-2.5 text-xs leading-relaxed text-muted-foreground">
              <input
                type="checkbox"
                className="mt-0.5 size-4 shrink-0 rounded border-input accent-[var(--primary)]"
                {...register("consent")}
              />
              <span>
                J&apos;accepte les{" "}
                <Link href="/cgv" target="_blank" className="text-navy underline underline-offset-2">CGV</Link>.
              </span>
            </label>
            {errors.consent && <p className="text-xs text-destructive">{errors.consent.message}</p>}
          </div>

          <div className="space-y-1.5">
            <label className="flex items-start gap-2.5 text-xs leading-relaxed text-muted-foreground">
              <input
                type="checkbox"
                className="mt-0.5 size-4 shrink-0 rounded border-input accent-[var(--primary)]"
                {...register("consent_donnees")}
              />
              <span>
                Je consens au{" "}
                <Link href="/confidentialite" target="_blank" className="text-navy underline underline-offset-2">
                  traitement de mes données
                </Link>.
              </span>
            </label>
            {errors.consent_donnees && <p className="text-xs text-destructive">{errors.consent_donnees.message}</p>}
          </div>
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

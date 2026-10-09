"use client"

import { useEffect, useRef, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { ArrowRight, X } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { api, ApiError } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { held, type FormInputs } from "@/lib/held"
import { cn } from "@/lib/utils"
import type { Analysis } from "@/types"

export type DoorId = "account" | "advisor" | "promo" | "anonymous"

/** The promo code survives the sign-in round trip in this browser — the
 *  verification link opens a new tab, so not sessionStorage — for two hours,
 *  and never rides in a URL or a mail (four-doors spec, decision 34). */
const PROMO_KEY = "neoori_promo"
const PROMO_TTL_MS = 2 * 60 * 60 * 1000

const DOORS: { id: DoorId; title: string }[] = [
  { id: "account", title: "Avec mon compte" },
  { id: "advisor", title: "J'ai un code conseiller" },
  { id: "promo", title: "J'ai un code promo" },
  { id: "anonymous", title: "Sans compte" },
]

const WRONG_FOR_PROMO = "Ce code est un code conseiller : choisissez « J'ai un code conseiller »."
const THROTTLED = "Trop de tentatives — réessayez dans une minute."

function readPromo(): string {
  try {
    const saved = JSON.parse(localStorage.getItem(PROMO_KEY) ?? "null") as { code: string; at: number } | null
    if (!saved || Date.now() - saved.at > PROMO_TTL_MS) return ""
    return saved.code
  } catch { return "" }
}
function writePromo(value: string | null) {
  try {
    if (value === null) localStorage.removeItem(PROMO_KEY)
    else localStorage.setItem(PROMO_KEY, JSON.stringify({ code: value, at: Date.now() }))
  } catch { /* private mode: the person retypes it */ }
}

function Consent({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-start gap-2.5 text-xs leading-relaxed text-muted-foreground">
      <input
        type="checkbox"
        className="mt-0.5 size-4 shrink-0 rounded border-input accent-[var(--primary)]"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span>
        J’accepte les{" "}
        <Link href="/cgv" target="_blank" className="text-navy underline underline-offset-2">CGV</Link>{" "}
        et la{" "}
        <Link href="/confidentialite" target="_blank" className="text-navy underline underline-offset-2">politique de confidentialité</Link>.
      </span>
    </label>
  )
}

/** The four doors behind « Générer mon analyse » (four-doors spec). The
 *  server decides each door's tier and recipient; this only collects what
 *  the door needs and goes where the door leads. */
export function DoorsPanel({
  inputs,
  draftId,
  initialDoor,
  onClose,
}: {
  /** The form's current values, read at the moment a door is used. */
  inputs: () => FormInputs
  /** The signed-in caller's draft, promoted by the submit. */
  draftId: string | null
  initialDoor: DoorId | null
  onClose: () => void
}) {
  const router = useRouter()
  const { user } = useAuth()
  const signedIn = user !== null
  const doors = DOORS.filter((d) => !(signedIn && d.id === "anonymous"))

  const [open, setOpen] = useState<DoorId | null>(initialDoor)
  const [prenom, setPrenom] = useState("")
  const [nom, setNom] = useState("")
  const [code, setCode] = useState(readPromo)
  const [consent, setConsent] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [retried, setRetried] = useState(false)

  // The panel opens under the form's button, which on most screens is past the
  // fold: without this, « Générer mon analyse » seems to do nothing. The
  // global scroll-behavior (smooth, off under reduced motion) applies.
  const panel = useRef<HTMLElement>(null)
  useEffect(() => { panel.current?.scrollIntoView({ block: "start" }) }, [])

  const choose = (id: DoorId) => { setOpen(id); setError(null) }

  /** Sign in, then come back to the form with the draft held by the cookie. */
  const roundTrip = async (door: "account" | "promo") => {
    await held.saveDraft(inputs())
    const back = `/analyse/nouveau?reprendre=${door === "promo" ? "promo" : "compte"}`
    router.push(`/inscription?redirect=${encodeURIComponent(back)}`)
  }

  const submit = (door: DoorId, extra: Record<string, unknown> = {}) =>
    api.post<{ analysis?: Analysis; access_token?: string }>(
      "/analyses/",
      { inputs: inputs(), door, draft_id: draftId ?? undefined, ...extra },
      { skipRedirect: true },
    )

  const fail = (e: unknown) => {
    if (!(e instanceof ApiError)) { setError("Erreur inattendue."); return }
    const other = e.body?.door
    if (e.status === 409 && (other === "promo" || other === "advisor")) setOpen(other)
    setError(e.status === 429 && !e.body?.error ? THROTTLED : e.message)
  }

  // `busy` is released only where the person stays on this page. A request the
  // server accepted ends in a navigation, and router.push returns before the
  // next page has loaded: releasing the button there let a second click start a
  // second run (or spend a second use of a code) while the first was loading.
  const go = async () => {
    if (!open) return
    setBusy(true)
    setError(null)
    try {
      if (open === "account") {
        if (!signedIn) return await roundTrip("account")
        const res = await submit("account")
        router.push(`/analyse/en-cours/${res.analysis!.id}`)
      } else if (open === "promo") {
        const check = await api.post<{ kind: "promo" | "conseiller" }>("/codes/check", { code }, { skipRedirect: true })
        if (check.kind !== "promo") { setOpen("advisor"); setError(WRONG_FOR_PROMO); setBusy(false); return }
        if (!signedIn) { writePromo(code); return await roundTrip("promo") }
        const res = await submit("promo", { code })
        writePromo(null)
        router.push(`/analyse/en-cours/${res.analysis!.id}`)
      } else if (open === "advisor") {
        await submit("advisor", { code, prenom, nom, consent })
        router.push("/analyse/envoyee")
      } else {
        const res = await submit("anonymous", { consent })
        router.push(`/rapport#${res.access_token}`)
      }
    } catch (e) {
      // A session that lapsed between the page load and the click: sign in
      // again, once (four-doors spec, decision 38).
      if (e instanceof ApiError && e.status === 401 && (open === "account" || open === "promo") && !retried) {
        setRetried(true)
        try { await roundTrip(open) } catch (again) { setBusy(false); fail(again) }
      } else {
        setBusy(false)
        fail(e)
      }
    }
  }

  const field = (
    id: string, label: string, value: string, set: (v: string) => void,
    extra: Partial<React.ComponentProps<typeof Input>> = {},
  ) => (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} className="h-10" value={value} onChange={(e) => set(e.target.value)} disabled={busy} {...extra} />
    </div>
  )

  const body = (id: DoorId) => {
    switch (id) {
      case "account":
        return (
          <>
            <p className="text-sm text-muted-foreground">
              Version gratuite : les trois premières sections et le verdict, gardés dans votre espace. Le rapport complet reste disponible à 9 €.
            </p>
            <Button onClick={go} disabled={busy} size="lg">
              {signedIn ? "Lancer la version gratuite" : "Créer un compte ou me connecter"} <ArrowRight />
            </Button>
          </>
        )
      case "advisor":
        return (
          <>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {field("door-prenom", "Prénom", prenom, setPrenom, { maxLength: 80, autoComplete: "given-name" })}
              {field("door-nom", "Nom", nom, setNom, { maxLength: 80, autoComplete: "family-name" })}
            </div>
            {field("door-code-conseiller", "Code", code, setCode, { autoComplete: "off", placeholder: "ex. A1B2C3D4" })}
            <p className="rounded-lg bg-peach-soft p-3 text-xs leading-relaxed text-navy">
              {"Le rapport complet sera envoyé à votre conseiller, pas à vous : vous n'en recevrez pas de copie. Votre conseiller pourra vous le présenter ou vous le transmettre."}
            </p>
            <Consent checked={consent} onChange={setConsent} />
            <Button onClick={go} size="lg" disabled={busy || !consent || !prenom.trim() || !nom.trim() || !code.trim()}>
              Envoyer à mon conseiller <ArrowRight />
            </Button>
          </>
        )
      case "promo":
        return (
          <>
            <p className="text-sm text-muted-foreground">Le rapport complet, offert. Un compte est nécessaire pour le recevoir.</p>
            {field("door-code-promo", "Code", code, setCode, { autoComplete: "off", placeholder: "ex. A1B2C3D4" })}
            <Button onClick={go} size="lg" disabled={busy || !code.trim()}>
              {signedIn ? "Lancer l’analyse complète" : "Continuer"} <ArrowRight />
            </Button>
          </>
        )
      case "anonymous":
        return (
          <>
            <p className="text-sm text-muted-foreground">
              Version gratuite, accessible par un lien privé pendant 30 jours. Sans compte, nous ne pourrons pas vous renvoyer ce lien.
            </p>
            <Consent checked={consent} onChange={setConsent} />
            <Button onClick={go} size="lg" disabled={busy || !consent}>
              Lancer sans compte <ArrowRight />
            </Button>
          </>
        )
    }
  }

  return (
    <section ref={panel} aria-labelledby="doors-title" className="scroll-mt-24 rounded-2xl bg-card p-5 shadow-soft ring-1 ring-foreground/10">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 id="doors-title" className="font-display text-lg font-bold text-navy">Comment voulez-vous continuer ?</h2>
        <Button variant="ghost" size="icon-sm" aria-label="Fermer" onClick={onClose}><X className="size-4" /></Button>
      </div>
      {error && <Alert variant="destructive" className="mb-4"><AlertDescription>{error}</AlertDescription></Alert>}
      <div className="space-y-3">
        {doors.map((d) => (
          <div key={d.id} className={cn("rounded-xl border", open === d.id ? "border-navy" : "border-border")}>
            <button
              type="button"
              aria-expanded={open === d.id}
              onClick={() => choose(d.id)}
              className="w-full px-4 py-3 text-left text-sm font-semibold text-navy"
            >
              {d.title}
            </button>
            {open === d.id && <div className="space-y-3 border-t border-border px-4 py-4">{body(d.id)}</div>}
          </div>
        ))}
      </div>
    </section>
  )
}

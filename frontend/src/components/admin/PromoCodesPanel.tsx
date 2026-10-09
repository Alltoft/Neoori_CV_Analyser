"use client"

import { useEffect, useState } from "react"
import { Check, Copy } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { api, ApiError } from "@/lib/api"
import { fmtDate } from "@/lib/format"
import { copyToClipboard, parseUtc } from "@/lib/utils"
import type { AdminCodeRow } from "@/types"

/** An empty field means illimité, as the API's null does. Anything that is
 *  not a positive whole number goes as 0, which the API refuses with its own
 *  sentence — never as NaN, which JSON turns into null, i.e. illimité. */
const limit = (raw: string): number | null => {
  if (raw.trim() === "") return null
  const n = Number(raw)
  return Number.isInteger(n) && n > 0 ? n : 0
}

/** Revoked, however it came to be: a code the admin revoked has `revoked_at`,
 *  but one deactivated before that column existed has only `is_active` false.
 *  The server refuses both alike, so the table must read and act on both alike. */
const isRevoked = (c: AdminCodeRow) => Boolean(c.revoked_at) || !c.is_active

function statut(c: AdminCodeRow): string {
  if (isRevoked(c)) return "Révoqué"
  // expires_at is a naive UTC string: parseUtc, since new Date() reads it as local time.
  if (c.expires_at && parseUtc(c.expires_at) <= new Date()) return "Expiré"
  return "Actif"
}

/** The admin's codes (four-doors spec, decision 18). A code with no owner is
 *  a promo code: signed in, Complet, once per account. Conseiller codes are
 *  listed for reference; their limits are the conseiller's. */
export function PromoCodesPanel() {
  const [codes, setCodes] = useState<AdminCodeRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [label, setLabel] = useState("")
  const [uses, setUses] = useState("1")
  const [days, setDays] = useState("90")
  const [busy, setBusy] = useState(false)
  const [copied, setCopied] = useState<string | null>(null)
  const [editing, setEditing] = useState<{ id: string; uses: string; days: string } | null>(null)
  const [revoking, setRevoking] = useState<string | null>(null)

  useEffect(() => {
    api.get<{ codes: AdminCodeRow[] }>("/admin/counselor-codes")
      .then((r) => setCodes(r.codes))
      .catch((e) => setError(e instanceof ApiError ? e.message : "Erreur de chargement"))
      .finally(() => setLoading(false))
  }, [])

  const replace = (row: AdminCodeRow) => setCodes((all) => all.map((c) => (c.id === row.id ? row : c)))
  const fail = (e: unknown) => setError(e instanceof ApiError ? e.message : "Erreur inattendue.")

  const create = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const r = await api.post<{ code: AdminCodeRow }>("/admin/counselor-codes", {
        label, max_uses: limit(uses), expires_in_days: limit(days),
      })
      setCodes((all) => [r.code, ...all])
      setLabel("")
    } catch (err) { fail(err) } finally { setBusy(false) }
  }

  const saveLimits = async () => {
    if (!editing) return
    setBusy(true)
    setError(null)
    try {
      // Validity left empty while editing means "unchanged", not illimité.
      const body: Record<string, number | null> = { max_uses: limit(editing.uses) }
      if (editing.days.trim()) body.expires_in_days = limit(editing.days)
      const r = await api.patch<{ code: AdminCodeRow }>(`/admin/counselor-codes/${editing.id}`, body)
      replace(r.code)
      setEditing(null)
    } catch (err) { fail(err) } finally { setBusy(false) }
  }

  const revoke = async (id: string) => {
    setBusy(true)
    setError(null)
    try {
      const r = await api.delete<{ code: AdminCodeRow }>(`/admin/counselor-codes/${id}`)
      replace(r.code)
      setRevoking(null)
    } catch (err) { fail(err) } finally { setBusy(false) }
  }

  const copy = async (value: string) => {
    if (await copyToClipboard(value)) {
      setCopied(value)
      setTimeout(() => setCopied(null), 2000)
    }
  }

  return (
    <section className="rounded-2xl bg-card shadow-soft ring-1 ring-foreground/10">
      <div className="border-b border-border px-5 py-4">
        <h2 className="font-display text-base font-semibold text-navy">Codes promo</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Un code promo donne le rapport complet, une fois par compte. Un champ vide signifie « illimité ».
        </p>
      </div>
      <div className="px-5 py-4">
        {error && <Alert variant="destructive" className="mb-4"><AlertDescription>{error}</AlertDescription></Alert>}

        <form onSubmit={create} className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex-1 space-y-1.5">
            <Label htmlFor="promo-label">Libellé</Label>
            <Input id="promo-label" className="h-10" value={label} disabled={busy}
                   onChange={(e) => setLabel(e.target.value)} placeholder="Salon, partenaire, relecture PM…" />
          </div>
          <div className="w-full space-y-1.5 sm:w-28">
            <Label htmlFor="promo-uses">Utilisations</Label>
            <Input id="promo-uses" type="number" min={1} className="h-10" value={uses} disabled={busy}
                   onChange={(e) => setUses(e.target.value)} />
          </div>
          <div className="w-full space-y-1.5 sm:w-28">
            <Label htmlFor="promo-days">Validité (jours)</Label>
            <Input id="promo-days" type="number" min={1} className="h-10" value={days} disabled={busy}
                   onChange={(e) => setDays(e.target.value)} />
          </div>
          <Button type="submit" variant="navy" size="lg" disabled={busy || !label.trim()}>Créer le code</Button>
        </form>

        <div className="w-full overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left">
                {["Code", "Libellé", "Type", "Analyses", "Voyages", "Limite", "Expire le", "Statut", ""].map((h) => (
                  <th key={h} className="eyebrow pb-2 pr-4 font-medium text-muted-foreground">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {codes.map((c) => {
                const isEditing = editing?.id === c.id
                return (
                  <tr key={c.id} className="border-b border-border/60 last:border-0">
                    <td className="whitespace-nowrap py-2.5 pr-4 font-mono text-xs">
                      {c.code}{" "}
                      <button type="button" aria-label="Copier le code" onClick={() => copy(c.code)}>
                        {copied === c.code ? <Check className="inline size-3.5 text-success" /> : <Copy className="inline size-3.5" />}
                      </button>
                    </td>
                    <td className="py-2.5 pr-4">{c.label}</td>
                    <td className="py-2.5 pr-4"><Badge variant="outline">{c.kind === "promo" ? "Promo" : "Conseiller"}</Badge></td>
                    <td className="py-2.5 pr-4 tabular-nums">{c.uses_by_kind.analysis}</td>
                    <td className="py-2.5 pr-4 tabular-nums">{c.uses_by_kind.voyage}</td>
                    <td className="py-2.5 pr-4">
                      {isEditing
                        ? <Input className="h-8 w-20" type="number" min={1} aria-label="Utilisations" value={editing.uses}
                                 onChange={(e) => setEditing({ ...editing, uses: e.target.value })} />
                        : (c.max_uses ?? "illimité")}
                    </td>
                    <td className="py-2.5 pr-4">
                      {isEditing
                        ? <Input className="h-8 w-24" type="number" min={1} aria-label="Validité (jours)" placeholder="inchangé" value={editing.days}
                                 onChange={(e) => setEditing({ ...editing, days: e.target.value })} />
                        : fmtDate(c.expires_at)}
                    </td>
                    <td className="py-2.5 pr-4">{statut(c)}</td>
                    <td className="whitespace-nowrap py-2.5 text-right">
                      {c.kind === "promo" && !isRevoked(c) && (
                        isEditing ? (
                          <>
                            <Button size="sm" variant="navy" onClick={saveLimits} disabled={busy}>Enregistrer</Button>{" "}
                            <Button size="sm" variant="ghost" onClick={() => setEditing(null)}>Annuler</Button>
                          </>
                        ) : revoking === c.id ? (
                          <>
                            <span className="text-xs">Révoquer ce code ?</span>{" "}
                            <Button size="sm" variant="destructive" onClick={() => revoke(c.id)} disabled={busy}>Révoquer</Button>{" "}
                            <Button size="sm" variant="ghost" onClick={() => setRevoking(null)}>Annuler</Button>
                          </>
                        ) : (
                          <>
                            <Button size="sm" variant="outline"
                                    onClick={() => setEditing({ id: c.id, uses: c.max_uses?.toString() ?? "", days: "" })}>
                              Limites
                            </Button>{" "}
                            <Button size="sm" variant="ghost" onClick={() => setRevoking(c.id)}>Révoquer</Button>
                          </>
                        )
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        {!loading && codes.length === 0 && (
          <p className="py-10 text-center text-sm text-muted-foreground">Aucun code pour le moment.</p>
        )}
      </div>
    </section>
  )
}

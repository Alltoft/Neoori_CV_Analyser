"use client"

import { useCallback, useEffect, useState } from "react"
import { PromoCodesPanel } from "@/components/admin/PromoCodesPanel"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { StatCard } from "@/components/ui/stat-card"
import { api, ApiError } from "@/lib/api"
import { adminCounselor } from "@/lib/counselor"
import { fmtDate, fmtInt } from "@/lib/format"
import type { User } from "@/types"
import type { CounselorApplication, DomaineActivite, TypeStructure } from "@/types"
import { Textarea } from "@/components/ui/textarea"
import { Ban, Check, ClipboardList, UserCheck, Users } from "lucide-react"

// French labels for the demande's structure-type field, typed as a Record so
// TypeScript flags any TypeStructure member left uncovered.
const TYPE_STRUCTURE_LABELS: Record<TypeStructure, string> = {
  cap_emploi: "Cap Emploi / OPS",
  mission_locale: "Mission locale",
  france_travail: "France Travail",
  association: "Association",
  esat_ea: "ESAT / Entreprise adaptée",
  formation_cfa: "Organisme de formation / CFA",
  etablissement_scolaire: "Établissement scolaire ou universitaire",
  collectivite: "Collectivité / service public",
  medico_social: "Structure médico-sociale ou de santé",
  entreprise_rh: "Entreprise / cabinet RH, recrutement, intérim",
  organisation_pro: "Organisation professionnelle / OPCO / syndicat",
  independant: "Indépendant / auto-entrepreneur / consultant",
  autre: "Autre",
}

// French labels for the demande's domaines d’activité, same Record discipline.
const DOMAINE_LABELS: Record<DomaineActivite, string> = {
  insertion_emploi: "Insertion / emploi",
  handicap: "Handicap",
  orientation_bilan: "Orientation / bilan de compétences",
  formation: "Formation",
  recrutement_entreprises: "Recrutement / relations entreprises",
  accompagnement_social: "Accompagnement social / médico-social",
  education: "Éducation",
  autre: "Autre",
}

// type_structure is nullable (demandes filed before this field existed), and
// for "autre" the useful label is the free-text answer, not the bare word
// "Autre".
function typeStructureLabel(
  type: TypeStructure | null,
  autre: string | null
): string | null {
  if (!type) return null
  const label = TYPE_STRUCTURE_LABELS[type] ?? type
  return type === "autre" && autre ? `${label} — ${autre}` : label
}

// rue / code postal / ville are each independently nullable; join whichever
// parts are present instead of requiring all three.
function adresseLine(
  rue: string | null,
  codePostal: string | null,
  ville: string | null
): string | null {
  const cpVille = [codePostal, ville].filter(Boolean).join(" ")
  const parts = [rue, cpVille].filter(Boolean)
  return parts.length > 0 ? parts.join(", ") : null
}

export default function ConseillersPage() {
  const [counselors, setCounselors] = useState<User[]>([])
  const [loadingCounselors, setLoadingCounselors] = useState(true)
  const [errorCounselors, setErrorCounselors] = useState<string | null>(null)

  const [applications, setApplications] = useState<CounselorApplication[]>([])
  const [loadingApps, setLoadingApps] = useState(true)
  const [decidingId, setDecidingId] = useState<string | null>(null)
  // Per-row draft inputs, keyed by application id, so two open rows don't share
  // one box.
  const [limits, setLimits] = useState<Record<string, { codes: string; uses: string }>>({})
  const [reasons, setReasons] = useState<Record<string, string>>({})
  // Per-panel error state, matching errorCounselors/errorCodes below: an
  // error from one of the four demande/compte actions must surface in the
  // panel that produced it, not a screen away in Comptes conseillers.
  const [errorDemandes, setErrorDemandes] = useState<string | null>(null)
  const [errorApproved, setErrorApproved] = useState<string | null>(null)

  const loadApplications = useCallback(() => {
    setLoadingApps(true)
    adminCounselor.list("pending")
      .then(r => setApplications(r.applications))
      .catch(err => setErrorCounselors(err?.message ?? "Erreur de chargement"))
      .finally(() => setLoadingApps(false))
  }, [])

  useEffect(() => { loadApplications() }, [loadApplications])

  // Blank means illimité. Anything else is validated rather than coerced:
  // turning a typed 0 into null would read as "unlimited" to the API — the
  // exact opposite of what an admin typing 0 intends, on a spend control.
  const toLimit = (raw: string | undefined): number | null | "invalid" => {
    const s = (raw ?? "").trim()
    if (!s) return null
    const n = Number(s)
    return Number.isInteger(n) && n > 0 ? n : "invalid"
  }

  const [approved, setApproved] = useState<CounselorApplication[]>([])

  const loadApproved = useCallback(() => {
    adminCounselor.list("approved")
      .then(r => {
        setApproved(r.applications)
        // Seed each row's draft boxes from what that account currently has.
        // Without this, pressing « Modifier les limites » without typing sends
        // two blanks — which the API reads as illimité, silently removing the
        // cap instead of leaving it alone.
        setLimits(p => {
          const next = { ...p }
          for (const a of r.applications) {
            if (next[a.id] === undefined) {
              next[a.id] = {
                codes: a.max_codes === null ? "" : String(a.max_codes),
                uses: a.max_uses_per_code === null ? "" : String(a.max_uses_per_code),
              }
            }
          }
          return next
        })
      })
      .catch(err => setErrorCounselors(err?.message ?? "Erreur de chargement"))
  }, [])

  useEffect(() => { loadApproved() }, [loadApproved])

  // Drop a row's draft motif once its decision goes through. Without this,
  // approving a demande whose refusal motif was half-typed carries that text
  // into the same account's revocation box in the Conseillers actifs panel —
  // and a later revoke would submit it as the revocation reason shown to the
  // conseiller, for a reason nobody actually wrote.
  const clearReason = (id: string) => {
    setReasons(p => {
      const { [id]: _drop, ...rest } = p
      return rest
    })
  }

  const handleApprove = useCallback(async (id: string) => {
    const codes = toLimit(limits[id]?.codes)
    const uses = toLimit(limits[id]?.uses)
    if (codes === "invalid" || uses === "invalid") {
      setErrorDemandes("Une limite doit être un entier supérieur à zéro.")
      return
    }
    setDecidingId(id)
    try {
      await adminCounselor.approve(id, codes, uses)
      clearReason(id)
      loadApplications()
      loadApproved()
    } catch (err) {
      setErrorDemandes(err instanceof ApiError ? err.message : "Erreur lors de l'approbation")
    } finally {
      setDecidingId(null)
    }
  }, [limits, loadApplications, loadApproved])

  const handleReject = useCallback(async (id: string) => {
    const reason = (reasons[id] ?? "").trim()
    if (!reason) {
      setErrorDemandes("Un motif est requis pour refuser une demande.")
      return
    }
    setDecidingId(id)
    try {
      await adminCounselor.reject(id, reason)
      clearReason(id)
      loadApplications()
    } catch (err) {
      setErrorDemandes(err instanceof ApiError ? err.message : "Erreur lors du refus")
    } finally {
      setDecidingId(null)
    }
  }, [reasons, loadApplications])

  const handleLimits = useCallback(async (id: string) => {
    const codes = toLimit(limits[id]?.codes)
    const uses = toLimit(limits[id]?.uses)
    if (codes === "invalid" || uses === "invalid") {
      setErrorApproved("Une limite doit être un entier supérieur à zéro.")
      return
    }
    setDecidingId(id)
    try {
      await adminCounselor.limits(id, codes, uses)
      loadApproved()
    } catch (err) {
      setErrorApproved(err instanceof ApiError ? err.message : "Erreur lors de la mise à jour")
    } finally {
      setDecidingId(null)
    }
  }, [limits, loadApproved])

  const handleRevoke = useCallback(async (id: string) => {
    const reason = (reasons[id] ?? "").trim()
    if (!reason) {
      setErrorApproved("Un motif est requis pour révoquer un accès conseiller.")
      return
    }
    if (!window.confirm(
      "Révoquer l’accès conseiller de ce compte ? Les codes déjà remis restent valables."
    )) return
    setDecidingId(id)
    try {
      await adminCounselor.revoke(id, reason)
      clearReason(id)
      loadApproved()
    } catch (err) {
      setErrorApproved(err instanceof ApiError ? err.message : "Erreur lors de la révocation")
    } finally {
      setDecidingId(null)
    }
  }, [reasons, loadApproved])

  // Fetch counselors
  useEffect(() => {
    api.get<{ users: User[] }>("/admin/users")
      .then(r => {
        const filtered = r.users.filter(u => u.role === "counselor")
        setCounselors(filtered)
      })
      .catch(err => setErrorCounselors(err?.message ?? "Erreur de chargement"))
      .finally(() => setLoadingCounselors(false))
  }, [])

  return (
    <>
      {/* Page header */}
      <div className="mb-6">
        <p className="eyebrow text-orange-dark">Administration</p>
        <h1 className="font-display font-bold text-2xl sm:text-3xl text-navy mt-1">
          Conseillers
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Demandes de comptes conseiller, comptes actifs, et codes d’accès créés directement.
        </p>
      </div>

      {/* Summary tiles */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 mb-6">
        <StatCard
          label="Conseillers"
          value={loadingCounselors ? "—" : fmtInt(counselors.length)}
          hint="Comptes actifs"
          icon={<Users className="size-4" />}
        />
      </div>

      <section className="mb-6 rounded-2xl bg-card ring-1 ring-foreground/10 shadow-soft">
        <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-4">
          <div className="flex items-center gap-2">
            <ClipboardList className="size-4 text-orange" />
            <h2 className="font-display text-base font-semibold text-navy">
              Demandes en attente
            </h2>
          </div>
          <span className="eyebrow text-muted-foreground">
            {applications.length} demande{applications.length !== 1 ? "s" : ""}
          </span>
        </div>

        <div className="px-5 py-4">
          {errorDemandes && (
            <div
              role="alert"
              className="mb-4 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
            >
              {errorDemandes}
            </div>
          )}

          {loadingApps && <Skeleton className="h-24" />}

          {!loadingApps && applications.length === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              Aucune demande en attente.
            </p>
          )}

          <div className="space-y-4">
            {applications.map(a => (
              <article key={a.id} className="rounded-xl border border-border p-4">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <div>
                    <h3 className="font-display font-semibold text-navy">{a.structure}</h3>
                    <p className="text-sm font-medium text-navy">
                      {a.nom_complet ?? "Non renseigné"}
                    </p>
                  </div>
                  <span className="font-mono text-xs text-muted-foreground">{fmtDate(a.created_at)}</span>
                </div>

                <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                  <div><dt className="eyebrow text-muted-foreground">Fonction</dt><dd className="text-navy">{a.fonction}</dd></div>
                  <div><dt className="eyebrow text-muted-foreground">Téléphone</dt><dd className="text-navy">{a.telephone}</dd></div>
                  <div><dt className="eyebrow text-muted-foreground">Email de connexion</dt><dd className="text-navy">{a.user.email}</dd></div>
                  {a.email_pro && (
                    <div><dt className="eyebrow text-muted-foreground">Email professionnel</dt><dd className="text-navy">{a.email_pro}</dd></div>
                  )}
                  <div>
                    <dt className="eyebrow text-muted-foreground">Type de structure</dt>
                    <dd className="text-navy">
                      {typeStructureLabel(a.type_structure, a.type_structure_autre) ?? "Non renseigné"}
                    </dd>
                  </div>
                  <div>
                    <dt className="eyebrow text-muted-foreground">SIRET</dt>
                    <dd className="font-mono text-navy">{a.siret ?? "Non renseigné"}</dd>
                  </div>
                  {adresseLine(a.adresse_rue, a.adresse_code_postal, a.adresse_ville) && (
                    <div className="sm:col-span-2">
                      <dt className="eyebrow text-muted-foreground">Adresse</dt>
                      <dd className="text-navy">
                        {adresseLine(a.adresse_rue, a.adresse_code_postal, a.adresse_ville)}
                      </dd>
                    </div>
                  )}
                  {a.domaines.length > 0 && (
                    <div className="sm:col-span-2">
                      <dt className="eyebrow text-muted-foreground">Domaines d’activité</dt>
                      <dd className="mt-1 flex flex-wrap gap-1.5">
                        {a.domaines.map(d => (
                          <Badge key={d} variant="secondary">{DOMAINE_LABELS[d] ?? d}</Badge>
                        ))}
                      </dd>
                    </div>
                  )}
                </dl>

                {a.message && (
                  <p className="mt-3 rounded-lg bg-secondary px-4 py-3 text-sm text-muted-foreground">
                    {a.message}
                  </p>
                )}

                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label htmlFor={`codes-${a.id}`}>Nombre de codes</Label>
                    <Input
                      id={`codes-${a.id}`} type="number" min={1} className="h-10" placeholder="Illimité"
                      value={limits[a.id]?.codes ?? ""}
                      onChange={e => setLimits(p => ({ ...p, [a.id]: { codes: e.target.value, uses: p[a.id]?.uses ?? "" } }))}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor={`uses-${a.id}`}>Utilisations par code</Label>
                    <Input
                      id={`uses-${a.id}`} type="number" min={1} className="h-10" placeholder="Illimité"
                      value={limits[a.id]?.uses ?? ""}
                      onChange={e => setLimits(p => ({ ...p, [a.id]: { codes: p[a.id]?.codes ?? "", uses: e.target.value } }))}
                    />
                  </div>
                </div>

                <div className="mt-3 space-y-1.5">
                  <Label htmlFor={`reason-${a.id}`}>Motif (requis pour refuser)</Label>
                  <Textarea
                    id={`reason-${a.id}`} rows={2}
                    value={reasons[a.id] ?? ""}
                    onChange={e => setReasons(p => ({ ...p, [a.id]: e.target.value }))}
                  />
                </div>

                <div className="mt-4 flex flex-wrap gap-2">
                  <Button variant="navy" size="lg" disabled={decidingId === a.id} onClick={() => handleApprove(a.id)}>
                    <Check className="size-4" />
                    {decidingId === a.id ? "…" : "Approuver"}
                  </Button>
                  <Button
                    variant="ghost" size="lg" disabled={decidingId === a.id} onClick={() => handleReject(a.id)}
                    className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                  >
                    <Ban className="size-4" />Refuser
                  </Button>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="mb-6 rounded-2xl bg-card ring-1 ring-foreground/10 shadow-soft">
        <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-4">
          <div className="flex items-center gap-2">
            <UserCheck className="size-4 text-orange" />
            <h2 className="font-display text-base font-semibold text-navy">
              Conseillers actifs
            </h2>
          </div>
          <span className="eyebrow text-muted-foreground">
            {approved.length} compte{approved.length !== 1 ? "s" : ""}
          </span>
        </div>

        <div className="px-5 py-4">
          {errorApproved && (
            <div
              role="alert"
              className="mb-4 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
            >
              {errorApproved}
            </div>
          )}

          {approved.length === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              Aucun conseiller actif.
            </p>
          )}

          <div className="space-y-4">
            {approved.map(a => (
              <article key={a.id} className="rounded-xl border border-border p-4">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <div>
                    <h3 className="font-display font-semibold text-navy">{a.structure}</h3>
                    <p className="text-sm text-muted-foreground">
                      {[a.nom_complet, typeStructureLabel(a.type_structure, a.type_structure_autre)]
                        .filter(Boolean)
                        .join(" · ") || "Non renseigné"}
                    </p>
                  </div>
                  <span className="text-sm text-muted-foreground">{a.user.email}</span>
                </div>

                <p className="mt-2 text-sm text-muted-foreground">
                  Codes : {a.max_codes ?? "illimité"} · Utilisations par code :{" "}
                  {a.max_uses_per_code ?? "illimité"}
                </p>

                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label htmlFor={`a-codes-${a.id}`}>Nombre de codes</Label>
                    <Input
                      id={`a-codes-${a.id}`} type="number" min={1} className="h-10" placeholder="Illimité"
                      value={limits[a.id]?.codes ?? ""}
                      onChange={e => setLimits(p => ({ ...p, [a.id]: { codes: e.target.value, uses: p[a.id]?.uses ?? "" } }))}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor={`a-uses-${a.id}`}>Utilisations par code</Label>
                    <Input
                      id={`a-uses-${a.id}`} type="number" min={1} className="h-10" placeholder="Illimité"
                      value={limits[a.id]?.uses ?? ""}
                      onChange={e => setLimits(p => ({ ...p, [a.id]: { codes: p[a.id]?.codes ?? "", uses: e.target.value } }))}
                    />
                  </div>
                </div>

                <div className="mt-3 space-y-1.5">
                  <Label htmlFor={`a-reason-${a.id}`}>Motif (requis pour révoquer)</Label>
                  <Textarea
                    id={`a-reason-${a.id}`} rows={2}
                    value={reasons[a.id] ?? ""}
                    onChange={e => setReasons(p => ({ ...p, [a.id]: e.target.value }))}
                  />
                </div>

                <div className="mt-4 flex flex-wrap gap-2">
                  <Button variant="outline" size="lg" disabled={decidingId === a.id}
                          onClick={() => handleLimits(a.id)}>
                    Modifier les limites
                  </Button>
                  <Button
                    variant="ghost" size="lg" disabled={decidingId === a.id}
                    onClick={() => handleRevoke(a.id)}
                    className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                  >
                    <Ban className="size-4" />Révoquer
                  </Button>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* One column: the codes table is 780 px wide, more than half this page's
          content width, and its actions sit in the last column. */}
      <div className="grid grid-cols-1 gap-6">
        {/* Counselors */}
        <section className="rounded-2xl bg-card ring-1 ring-foreground/10 shadow-soft">
          <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-4">
            <div className="flex items-center gap-2">
              <Users className="size-4 text-orange" />
              <h2 className="font-display font-semibold text-base text-navy">
                Comptes conseillers
              </h2>
            </div>
            <span className="eyebrow text-muted-foreground">
              {counselors.length} compte{counselors.length !== 1 ? "s" : ""}
            </span>
          </div>

          <div className="px-5 py-4">
            {errorCounselors && (
              <div
                role="alert"
                className="mb-4 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
              >
                {errorCounselors}
              </div>
            )}

            <div className="w-full overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left">
                    <th className="eyebrow pb-2 pr-4 font-medium text-muted-foreground">Email</th>
                    <th className="eyebrow pb-2 font-medium text-muted-foreground">Créé le</th>
                  </tr>
                </thead>
                <tbody>
                  {loadingCounselors
                    ? Array.from({ length: 4 }, (_, i) => (
                        <tr key={i} className="border-b border-border/60">
                          <td colSpan={2} className="py-2.5">
                            <Skeleton className="h-5" />
                          </td>
                        </tr>
                      ))
                    : counselors.map(c => (
                        <tr key={c.id} className="border-b border-border/60 last:border-0">
                          <td className="py-2.5 pr-4 text-navy">{c.email}</td>
                          <td className="py-2.5 font-mono text-xs text-muted-foreground whitespace-nowrap">
                            {fmtDate(c.created_at)}
                          </td>
                        </tr>
                      ))}
                </tbody>
              </table>
            </div>

            {!loadingCounselors && counselors.length === 0 && (
              <p className="py-10 text-center text-sm text-muted-foreground">
                Aucun conseiller inscrit pour le moment.
              </p>
            )}
          </div>
        </section>

        <PromoCodesPanel />
      </div>
    </>
  )
}

"use client"

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Skeleton } from "@/components/ui/skeleton"
import { ReportSection } from "@/components/report/ReportSection"
import { api } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { SECTION_TITLES } from "@/types"
import type { Analysis, CounselorNote } from "@/types"
import { Printer, ArrowLeft, Check } from "lucide-react"
import { Logo } from "@/components/brand/Logo"

export default function CounselorPage() {
  const { token } = useParams<{ token: string }>()
  const { user } = useAuth()
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [note, setNote] = useState<string>("")
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [saveError, setSaveError] = useState(false)

  useEffect(() => {
    api.get<{ analysis: Analysis }>(`/c/${token}`)
      .then((r) => setAnalysis(r.analysis))
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [token])

  useEffect(() => {
    if (!user) return
    api.get<{ note: CounselorNote | null }>(`/c/${token}/notes`)
      .then((r) => { if (r.note?.body) setNote(r.note.body) })
      .catch(() => {})
  }, [token, user])

  const saveNote = async () => {
    setSaving(true)
    setSaveError(false)
    try {
      await api.put(`/c/${token}/notes`, { body: note })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch {
      setSaveError(true)
    } finally {
      setSaving(false)
    }
  }

  const output = analysis?.output ?? {}
  const path = analysis?.inputs?._path ?? "A"
  const counselorSections = path === "B" ? ["1", "2", "8"] : ["1", "4", "5"]
  const name = analysis?.inputs?.prenom ?? analysis?.inputs?.nom ?? "—"

  if (error) {
    return (
      <div className="grid min-h-screen place-items-center bg-secondary px-5">
        <div className="max-w-sm rounded-2xl bg-card p-8 text-center ring-1 ring-foreground/10 shadow-card">
          <Logo className="mx-auto text-2xl" />
          <h1 className="mt-6 font-display text-lg font-bold text-navy">Lien invalide ou expiré</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Ce lien conseiller n’est plus valide. Demandez au candidat de le régénérer depuis son espace.
          </p>
          <Button render={<Link href="/" />} variant="outline" size="lg" className="mt-6">
            Retour à l’accueil
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-secondary">
      {/* Action bar */}
      <div className="no-print sticky top-0 z-40 flex items-center justify-between gap-3 border-b border-border bg-secondary/95 px-5 py-3 backdrop-blur-sm sm:px-8">
        {user ? (
          <Button render={<Link href="/espace" />} variant="ghost" size="sm">
            <ArrowLeft className="size-3.5" /> Mon espace
          </Button>
        ) : (
          <Logo className="text-lg" />
        )}
        <Button variant="outline" size="sm" disabled={loading} onClick={() => setTimeout(() => window.print(), 50)}>
          <Printer className="size-3.5" /> PDF synthèse
        </Button>
      </div>

      <div className="px-4 py-8">
        <div className="report-shell">
          <div className="report-rule" />

          {/* Navy header band */}
          <div className="bg-navy px-8 pb-6 pt-6 text-white">
            <div className="flex items-center justify-between gap-3">
              <Logo tone="light" className="text-base" />
              <Badge variant="peach">VERSION CONSEILLER</Badge>
            </div>
            <h1 className="mt-3 font-display text-2xl font-extrabold leading-tight text-white">
              Préparer un entretien · {name}
            </h1>
            <p className="mt-1 text-sm text-peach">
              Synthèse conseiller · à destination de Cap Emploi, Mission Locale, France Travail, CEP
            </p>
          </div>

          <div className="px-8 py-7">
            {/* Key facts */}
            {loading ? (
              <div className="mb-7 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-12" />)}
              </div>
            ) : analysis?.inputs ? (
              <div className="mb-7 grid grid-cols-1 gap-3 rounded-lg bg-secondary p-4 text-xs sm:grid-cols-2 lg:grid-cols-4">
                {(path === "B"
                  ? [
                      ["Sous-profil", analysis.inputs._sub_profile?.toUpperCase() ?? "—"],
                      ["Aime", (analysis.inputs.aime ?? []).join(", ").slice(0, 60) || "—"],
                      ["Refus", (analysis.inputs.refuse ?? []).join(", ").slice(0, 60) || "—"],
                      ["Accompagnement", analysis.inputs.accompagnement ?? "—"],
                    ]
                  : [
                      ["Cible visée", analysis.inputs.cible_visee?.slice(0, 50)],
                      ["Mobilité", Array.isArray(analysis.inputs.type_mobilite) ? analysis.inputs.type_mobilite.join(" + ") : analysis.inputs.type_mobilite],
                      ["Posture actuelle", analysis.inputs.situation_actuelle],
                      ["Points sensibles", analysis.inputs.notes_specifiques || "—"],
                    ]
                ).map(([k, v]) => (
                  <div key={k}>
                    <p className="eyebrow text-muted-foreground">{k}</p>
                    <p className="mt-1 font-semibold text-navy">{v}</p>
                  </div>
                ))}
              </div>
            ) : null}

            {/* Sections */}
            {counselorSections.map((n) => (
              <ReportSection
                key={n}
                n={n}
                title={output[n]?.title ?? SECTION_TITLES[n] ?? `Section ${n}`}
                section={loading ? undefined : output[n]}
                counselor
              />
            ))}

            {/* Counselor notes — never printed into the synthèse */}
            <div className="no-print rounded-lg border border-dashed border-border bg-card p-5">
              <h3 className="font-display text-sm font-semibold text-navy">Notes pour l’entretien</h3>
              <p className="mt-1 mb-3 text-xs italic text-muted-foreground">
                Champ libre · enregistré sur votre espace conseiller — non partagé avec le candidat.
              </p>
              {user ? (
                <>
                  <Textarea
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    placeholder="Vos observations, points à aborder en entretien…"
                    className="min-h-[100px] bg-background text-sm"
                  />
                  {saveError && <p className="mt-2 text-xs text-destructive">Échec de l’enregistrement. Réessayez.</p>}
                  <div className="mt-3 flex justify-end">
                    <Button size="sm" variant="outline" onClick={saveNote} disabled={saving}>
                      {saved ? <><Check className="size-3.5 text-success" /> Enregistré</> : saving ? "Enregistrement…" : "Enregistrer"}
                    </Button>
                  </div>
                </>
              ) : (
                <p className="text-sm text-muted-foreground">
                  <Link href="/connexion" className="text-primary underline">Connectez-vous</Link> pour écrire vos notes.
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

"use client"

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { api } from "@/lib/api"
import ReactMarkdown, { type Components } from "react-markdown"
import { useAuth } from "@/lib/auth"
import { SECTION_TITLES } from "@/types"
import type { Analysis, CounselorNote } from "@/types"
import { Printer } from "lucide-react"

export default function CounselorPage() {
  const { token } = useParams<{ token: string }>()
  const { user }  = useAuth()
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [note,     setNote]     = useState<string>("")
  const [loading,  setLoading]  = useState(true)
  const [saving,   setSaving]   = useState(false)
  const [saved,    setSaved]    = useState(false)

  useEffect(() => {
    api.get<{ analysis: Analysis }>(`/c/${token}`)
      .then(r => { setAnalysis(r.analysis) })
      .finally(() => setLoading(false))
  }, [token])

  useEffect(() => {
    if (!user) return
    api.get<{ note: CounselorNote | null }>(`/c/${token}/notes`)
      .then(r => { if (r.note?.body) setNote(r.note.body) })
      .catch(() => {})
  }, [token, user])

  const saveNote = async () => {
    setSaving(true)
    try {
      await api.put(`/c/${token}/notes`, { body: note })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } finally { setSaving(false) }
  }

  const output = analysis?.output ?? {}
  const path = analysis?.inputs?._path ?? "A"
  const counselorSections = path === "B" ? ["1", "2", "8"] : ["1", "4", "5"]

  return (
    <div className="min-h-screen bg-secondary">
      {/* Header */}
      <div className="no-print bg-background border-b border-border px-10 py-4 flex items-center justify-between sticky top-0 z-40">
        <div>
          <Badge className="bg-primary text-primary-foreground text-xs mb-1">VERSION CONSEILLER</Badge>
          <h1 className="font-bold text-lg">Préparer un entretien · {analysis?.inputs?.prenom ?? analysis?.inputs?.nom ?? "—"}</h1>
          <p className="text-xs text-muted-foreground">
            3 sections — 5 min de lecture · à destination Cap Emploi, Mission Locale, France Travail, CEP
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" className="text-xs" onClick={() => { setTimeout(() => window.print(), 50) }}>
            <Printer className="h-3.5 w-3.5 mr-1.5" />↓ PDF synthèse
          </Button>
        </div>
      </div>

      <div className="max-w-[820px] mx-auto px-8 py-8">
        {/* Key facts strip */}
        {loading ? (
          <div className="grid grid-cols-4 gap-4 mb-8">
            {[1,2,3,4].map(i => <Skeleton key={i} className="h-12" />)}
          </div>
        ) : analysis?.inputs && (
          <div className="grid grid-cols-4 gap-4 rounded-lg bg-card border border-border p-4 mb-8 text-xs">
            {(path === "B"
              ? [
                  ["Sous-profil",    analysis.inputs._sub_profile?.toUpperCase() ?? "—"],
                  ["Aime",           (analysis.inputs.aime ?? []).join(", ").slice(0, 60) || "—"],
                  ["Refus",          (analysis.inputs.refuse ?? []).join(", ").slice(0, 60) || "—"],
                  ["Accompagnement", analysis.inputs.accompagnement ?? "—"],
                ]
              : [
                  ["Cible visée",      analysis.inputs.cible_visee?.slice(0, 50)],
                  ["Mobilité",         Array.isArray(analysis.inputs.type_mobilite) ? analysis.inputs.type_mobilite.join(" + ") : analysis.inputs.type_mobilite],
                  ["Posture actuelle", analysis.inputs.situation_actuelle],
                  ["Points sensibles", analysis.inputs.notes_specifiques || "—"],
                ]
            ).map(([k, v]) => (
              <div key={k}>
                <p className="font-mono text-[10px] uppercase text-muted-foreground">{k}</p>
                <p className="font-semibold mt-1">{v}</p>
              </div>
            ))}
          </div>
        )}

        {/* Sections 1, 4, 5 */}
        {counselorSections.map(n => (
          <div key={n} className="mb-8">
            <div className="flex items-center gap-2 mb-3">
              <span className="inline-flex items-center justify-center w-7 h-7 rounded-full border-2 border-foreground text-xs font-bold font-mono shrink-0">
                §{n}
              </span>
              <h2 className="font-bold">{output[n]?.title ?? SECTION_TITLES[n]}</h2>
            </div>
            {loading ? (
              <div className="space-y-2 pl-9">
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-3 w-4/5" />
              </div>
            ) : output[n] ? (
              <div className="text-sm leading-relaxed pl-9 text-foreground/90">
                <ReactMarkdown
                  components={{
                    p:      ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                    ul:     ({ children }) => <ul className="list-disc pl-4 mb-2 space-y-1">{children}</ul>,
                    ol:     ({ children }) => <ol className="list-decimal pl-4 mb-2 space-y-1">{children}</ol>,
                    li:     ({ children }) => <li>{children}</li>,
                    strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                    em:     ({ children }) => <em className="italic">{children}</em>,
                    h3:     ({ children }) => <h3 className="font-semibold mt-3 mb-1">{children}</h3>,
                    h4:     ({ children }) => <h4 className="font-medium mt-2 mb-1">{children}</h4>,
                  } as Components}
                >
                  {output[n].body_markdown}
                </ReactMarkdown>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground pl-9">Section non disponible.</p>
            )}
            <Separator className="mt-6" />
          </div>
        ))}

        {/* Counselor notes */}
        <div className="rounded-lg border border-dashed border-border bg-card p-5">
          <h3 className="font-semibold text-sm mb-1">Notes pour l'entretien</h3>
          <p className="text-xs text-muted-foreground italic mb-3">
            champ libre · sauvegardé sur votre espace conseiller — non partagé avec le candidat
          </p>
          {user ? (
            <>
              <Textarea
                value={note}
                onChange={e => setNote(e.target.value)}
                placeholder="Vos observations, points à aborder en entretien…"
                className="min-h-[100px] text-sm bg-background"
              />
              <div className="flex justify-end mt-3">
                <Button size="sm" variant="outline" onClick={saveNote} disabled={saving}>
                  {saved ? "Enregistré ✓" : saving ? "Enregistrement…" : "Enregistrer"}
                </Button>
              </div>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">
              <a href="/connexion" className="text-primary underline">Connectez-vous</a>{" "}
              pour écrire vos notes.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

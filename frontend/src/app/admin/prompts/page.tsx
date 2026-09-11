"use client"

import { useCallback, useEffect, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import { Skeleton } from "@/components/ui/skeleton"
import { Separator } from "@/components/ui/separator"
import { api } from "@/lib/api"
import { fmtDate } from "@/lib/format"
import { cn } from "@/lib/utils"
import {
  ChevronDown,
  History,
  Info,
  RotateCcw,
  ShieldCheck,
  SquarePen,
} from "lucide-react"
import type { PromptSlot, PromptVersion } from "@/types"

const SLOTS: PromptSlot[] = ["1", "2", "3", "voyage_micro", "voyage_portrait"]

/**
 * Chip labels. These strings are a second copy of `LABELS` in
 * backend/app/services/prompt_slots.py and must stay byte-identical to it —
 * backend/tests/test_admin_selector_labels.py reads this file and fails if a
 * label drifts on either side. Edit both, or neither.
 */
const SLOT_LABEL: Record<PromptSlot, string> = {
  "1": "Parcours 1 · J'ai une cible",
  "2": "Parcours 2 · Je cherche ma direction",
  "3": "Parcours 3 · Je pars de zéro",
  voyage_micro: "Voyage · phrase (S0)",
  voyage_portrait: "Voyage · portrait",
}

/** What the selected prompt produces. Reads on from the label, which already
 *  names the slot — so no "Parcours N" prefix here, and no "parcours" at all
 *  for the voyage, which has no report sections. */
const SLOT_HELP: Record<PromptSlot, string> = {
  "1": "CV en main et cible identifiée. Rapport §1 à §9.",
  "2": "Un parcours mais pas de cible. Rapport §A à §G.",
  "3": "Sans CV, à partir des expériences de vie. Rapport §I à §VI.",
  voyage_micro:
    "La phrase écrite juste après la session 0, à partir des trois envies les plus marquées. Une seule phrase, 15 à 25 mots, modèle rapide.",
  voyage_portrait:
    "Les six sections rédigées après la session 5 : accroche, qui tu es, ce qui te fait vibrer, ce dont tu as besoin, les chemins possibles, ce que ton portrait ne dit pas encore. Le conseiller les relit et les valide avant que la personne les voie.",
}

/** Version-label suffix per slot; the history list groups on it. */
const SLOT_SUFFIX: Record<PromptSlot, string> = {
  "1": "-P1",
  "2": "-P2",
  "3": "-P3",
  voyage_micro: "-VM",
  voyage_portrait: "-VP",
}

const SUFFIX_RE = /-(?:P[123]|VM|VP|[AB])$/

/** Rows written before the v1.2 migration carry the old A/B codes. */
function toSlot(raw: string | undefined): PromptSlot {
  if (raw === "A") return "1"
  if (raw === "B") return "3"
  return (SLOTS as string[]).includes(raw ?? "") ? (raw as PromptSlot) : "1"
}

export default function PromptsPage() {
  const [versions, setVersions] = useState<PromptVersion[]>([])
  const [slot, setSlot] = useState<PromptSlot>("1")
  const [text, setText] = useState("")
  const [savedText, setSavedText] = useState("")
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [rollingBackId, setRollingBackId] = useState<string | null>(null)

  // Read-only preview of a past version's prompt text (expand/collapse).
  const [previewId, setPreviewId] = useState<string | null>(null)
  const [previewText, setPreviewText] = useState<Record<string, string>>({})
  const [previewLoadingId, setPreviewLoadingId] = useState<string | null>(null)
  const [previewError, setPreviewError] = useState<string | null>(null)

  const dirty = text !== savedText

  const loadData = useCallback(async (s: PromptSlot) => {
    const [pv, ap] = await Promise.all([
      api.get<{ prompts: PromptVersion[] }>("/prompts/"),
      api.get<{ prompt: PromptVersion }>(`/prompts/active?path=${s}`).catch(() => ({ prompt: null })),
    ])
    setVersions(pv.prompts)
    const t = ap.prompt?.system_prompt_text ?? ""
    setText(t)
    setSavedText(t)
    setError(null)
  }, [])

  useEffect(() => {
    setLoading(true)
    setPreviewId(null)
    setPreviewError(null)
    loadData(slot)
      .catch(err => setError(err?.message ?? "Erreur de chargement"))
      .finally(() => setLoading(false))
  }, [loadData, slot])

  const publish = async () => {
    if (!text.trim() || !dirty) return
    setSaving(true)
    setError(null)
    try {
      const activeVersion = versions.find(v => v.is_active && toSlot(v.path) === slot)
      // Every slot gets an explicit suffix. The old scheme left parcours A
      // unsuffixed, which made the strip regex asymmetric.
      const suffix = SLOT_SUFFIX[slot]
      const fallback = `v1.${new Date().toISOString().slice(0,10).replace(/-/g,"")}${suffix}`
      const lastLabel = activeVersion?.version_label ?? fallback
      const stripped = lastLabel.replace(SUFFIX_RE, "")
      const bumped = /^v\d+\.\d+$/.test(stripped)
        ? stripped.replace(/v(\d+)\.(\d+)/, (_, maj, min) => `v${maj}.${+min + 1}`)
        : `v1.${versions.filter(v => toSlot(v.path) === slot).length + 1}`
      const nextLabel = `${bumped}${suffix}`
      await api.post("/prompts/", {
        version_label: nextLabel,
        system_prompt_text: text,
        path: slot,
        activate: true,
      })
      await loadData(slot)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erreur lors de la publication")
    } finally {
      setSaving(false)
    }
  }

  const rollback = async (id: string) => {
    if (!window.confirm("Réactiver cette version comme prompt actif ? La version courante sera remplacée.")) return
    setRollingBackId(id)
    try {
      setError(null)
      await api.post(`/prompts/${id}/rollback`, {})
      await loadData(slot)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erreur lors du rollback")
    } finally {
      setRollingBackId(null)
    }
  }

  // Toggle the read-only preview; fetch the full text on first open.
  const togglePreview = async (v: PromptVersion) => {
    setPreviewError(null)
    if (previewId === v.id) {
      setPreviewId(null)
      return
    }
    setPreviewId(v.id)
    if (previewText[v.id] !== undefined) return
    setPreviewLoadingId(v.id)
    try {
      const res = await api.get<{ prompt: PromptVersion }>(`/prompts/${v.id}`)
      setPreviewText(prev => ({ ...prev, [v.id]: res.prompt?.system_prompt_text ?? "" }))
    } catch (err: unknown) {
      setPreviewError(err instanceof Error ? err.message : "Erreur lors du chargement de l’aperçu")
      setPreviewId(null)
    } finally {
      setPreviewLoadingId(null)
    }
  }

  const activeVersion = versions.find(v => v.is_active && toSlot(v.path) === slot)
  const visibleVersions = versions.filter(v => toSlot(v.path) === slot)

  return (
    <>
      <div className="mb-6">
        <p className="eyebrow text-orange-dark">Administration</p>
        <h1 className="font-display font-bold text-2xl sm:text-3xl text-navy mt-1">
          Prompts système
        </h1>
        <p className="text-sm text-muted-foreground mt-1.5 max-w-2xl">
          Modifiez le prompt envoyé au modèle, sans redéploiement. Chaque publication crée une
          nouvelle version conservée dans l’historique.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1.5fr_1fr]">
        {/* Editor */}
        <Card className="p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <SquarePen className="size-4 text-orange" aria-hidden />
                <h2 id="prompt-editor-label" className="font-display font-semibold text-base text-navy">
                  Éditeur du prompt
                </h2>
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                Éditable sans redéploiement · versionné · rollback possible
              </p>
            </div>
            {activeVersion ? (
              <Badge variant="peach" className="font-mono">
                {activeVersion.version_label} · actif
              </Badge>
            ) : (
              <Badge variant="outline" className="font-mono">
                aucune version active
              </Badge>
            )}
          </div>

          {/* Prompt selector */}
          <div className="mt-4">
            <span className="eyebrow text-navy-500">Prompt</span>
            <div
              role="group"
              aria-label="Sélection du prompt"
              className="flex flex-wrap gap-2 mt-2"
            >
              {SLOTS.map(s => (
                <button
                  key={s}
                  type="button"
                  aria-pressed={slot === s}
                  onClick={() => setSlot(s)}
                  className={cn(
                    "px-3 py-1.5 rounded-full border text-xs font-medium transition-colors",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
                    slot === s
                      ? "bg-navy border-navy text-white"
                      : "bg-background border-border text-muted-foreground hover:border-orange/50 hover:text-orange",
                  )}
                >
                  {SLOT_LABEL[s]}
                </button>
              ))}
            </div>
            <div className="mt-2.5 flex items-start gap-2 rounded-lg bg-peach-soft/60 px-3 py-2 text-xs text-navy-700">
              <Info className="size-3.5 mt-px shrink-0 text-orange-dark" aria-hidden />
              <p>
                Chaque prompt a sa propre structure de sortie et son propre historique. Vous
                éditez ici <span className="font-medium">{SLOT_LABEL[slot]}</span> :{" "}
                {SLOT_HELP[slot]}
              </p>
            </div>
          </div>

          <div className="mt-4">
            {loading ? (
              <Skeleton className="h-80" />
            ) : (
              <Textarea
                id="prompt-editor"
                aria-labelledby="prompt-editor-label"
                value={text}
                onChange={e => setText(e.target.value)}
                className="min-h-[340px] font-mono text-xs leading-relaxed bg-secondary resize-y"
                placeholder="Collez ici le texte complet du system prompt…"
              />
            )}
          </div>

          {error && (
            <div
              role="alert"
              className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive mt-4"
            >
              {error}
            </div>
          )}

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <Button
              variant="navy"
              size="sm"
              disabled={!dirty || saving || loading}
              onClick={publish}
            >
              {saving ? "Publication…" : "Publier la nouvelle version"}
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={!dirty || saving}
              onClick={() => setText(savedText)}
            >
              Annuler les modifications
            </Button>
            {!dirty && !loading && (
              <span className="text-xs text-muted-foreground">
                Modifiez le texte pour activer la publication.
              </span>
            )}
          </div>

          <Separator className="my-4" />

          <p className="flex items-start gap-2 text-xs text-muted-foreground">
            <ShieldCheck className="size-3.5 mt-px shrink-0 text-navy-500" aria-hidden />
            <span>
              Traçabilité B2G : chaque analyse enregistre la version de prompt utilisée.
            </span>
          </p>
        </Card>

        {/* Version history */}
        <Card className="p-5">
          <div className="flex items-center gap-2">
            <History className="size-4 text-orange" aria-hidden />
            <h2 className="font-display font-semibold text-base text-navy">
              Historique des versions
            </h2>
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Dépliez une version pour la prévisualiser en lecture seule avant un rollback.
          </p>

          {previewError && (
            <div
              role="alert"
              className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive mt-3"
            >
              {previewError}
            </div>
          )}

          <div className="mt-4">
            {loading ? (
              Array(4).fill(0).map((_, i) => <Skeleton key={i} className="h-12 mb-2" />)
            ) : visibleVersions.length === 0 ? (
              <p className="text-sm text-muted-foreground py-6 text-center">
                Aucune version pour « {SLOT_LABEL[slot]} ».
              </p>
            ) : (
              <ul className="flex flex-col">
                {visibleVersions.map(v => {
                  const expanded = previewId === v.id
                  return (
                    <li
                      key={v.id}
                      className="border-b border-dashed border-border py-3 last:border-0"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-xs font-medium text-navy">
                          {v.version_label}
                        </span>
                        {v.is_active && (
                          <Badge variant="peach" className="font-mono">
                            actif
                          </Badge>
                        )}
                        <span className="text-xs text-muted-foreground flex-1 min-w-[8rem]">
                          {v.author ?? "—"} · {fmtDate(v.created_at)}
                        </span>
                        <Button
                          variant="ghost"
                          size="xs"
                          aria-expanded={expanded}
                          aria-controls={`preview-${v.id}`}
                          onClick={() => togglePreview(v)}
                        >
                          {expanded ? "Masquer" : "Aperçu"}
                          <ChevronDown
                            className={cn(
                              "size-3 transition-transform",
                              expanded && "rotate-180",
                            )}
                            aria-hidden
                          />
                        </Button>
                        {!v.is_active && (
                          <Button
                            variant="outline"
                            size="xs"
                            disabled={rollingBackId !== null}
                            onClick={() => rollback(v.id)}
                          >
                            <RotateCcw className="size-3" aria-hidden />
                            {rollingBackId === v.id ? "…" : "Rollback"}
                          </Button>
                        )}
                      </div>

                      {expanded && (
                        <div id={`preview-${v.id}`} className="mt-3">
                          {previewLoadingId === v.id ? (
                            <Skeleton className="h-32" />
                          ) : (
                            <pre className="max-h-72 overflow-auto rounded-lg border border-border bg-secondary px-3 py-2.5 font-mono text-xs leading-relaxed text-foreground whitespace-pre-wrap break-words">
                              {previewText[v.id]?.trim()
                                ? previewText[v.id]
                                : "(version vide)"}
                            </pre>
                          )}
                          <p className="mt-1.5 text-xs text-muted-foreground">
                            Lecture seule. Utilisez « Rollback » pour réactiver cette version.
                          </p>
                        </div>
                      )}
                    </li>
                  )
                })}
              </ul>
            )}
          </div>
        </Card>
      </div>
    </>
  )
}

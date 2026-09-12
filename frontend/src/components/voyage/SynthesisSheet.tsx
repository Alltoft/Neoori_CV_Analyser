"use client"

import type { ReactNode } from "react"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import {
  AXIS_ROWS,
  BIG5_ROWS,
  LEVEL_HIGH,
  LEVEL_LOW,
  S4_ROWS,
  S5_ROWS,
  SCHWARTZ_LABELS,
  SDT_ROWS,
  STYLE_LABELS,
} from "@/lib/voyage-labels"
import type { MicroStatus, VoyageSynthesis } from "@/types/voyage"

import { RiasecBars } from "./RiasecBars"

const DASH = "—"

const join = (parts: (string | undefined)[], sep = " · ") =>
  parts.filter(Boolean).join(sep) || DASH

const signed = (n: number) => (n > 0 ? `+${n}` : String(n))

const sdtLabel = (key: string) => SDT_ROWS.find((r) => r.key === key)?.label ?? key
const big5Label = (key: string) => BIG5_ROWS.find((r) => r.key === key)?.label ?? key

// ── Phase-4 ruling R6 — marking AI-written text ──────────────────────────────
// The session-0 phrase (and, from Task 8, the six portrait sections) is the
// only candidate-facing generated text with no human gate before the person
// reads it. These strings sit in TS constants rather than bare JSX text so
// their straight apostrophes never trip react/no-unescaped-entities.
const AI_LEGEND =
  "Les blocs teintés sont rédigés par l'IA. La phrase a déjà été montrée à la personne, sans relecture préalable. Le portrait est un brouillon : il ne lui parvient qu'une fois que vous l'avez validé."
const PHRASE_MARKER = "Déjà affichée à la personne"
const PHRASE_FALLBACK = "La phrase n'a pas pu être rédigée."

// ── Ruling R10 — a row can be scored under a bank version that has since
// been retired. synthesis.scoring_version is always the bank's *current*
// value, so only the row's own version (passed in separately) can catch it.
const STALE_WARNING =
  "Ces réponses ont été enregistrées avec une version antérieure du questionnaire ; certaines sections peuvent apparaître incomplètes."

/** The values just under the dominant one — the manual's « Secondaire » cell. */
function secondary(counts: Record<string, number>, dominant: string[]): string[] {
  const top = dominant.length > 0 ? counts[dominant[0]] ?? 0 : 0
  const below = Object.entries(counts).filter(([, n]) => n > 0 && n < top)
  if (below.length === 0) return []
  const best = Math.max(...below.map(([, n]) => n))
  return below.filter(([, n]) => n === best).map(([key]) => key)
}

function Block({
  title,
  subtitle,
  children,
}: {
  title: string
  subtitle?: string
  children: ReactNode
}) {
  return (
    <section className="print-break mt-5 rounded-lg border border-border p-4">
      <h3 className="font-display text-sm font-semibold text-navy">{title}</h3>
      {subtitle ? <p className="mt-0.5 text-xs text-muted-foreground">{subtitle}</p> : null}
      <div className="mt-3">{children}</div>
    </section>
  )
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="eyebrow text-muted-foreground">{label}</p>
      <p className="mt-1 text-sm font-medium text-navy">{value || DASH}</p>
    </div>
  )
}

function Missing({ n }: { n: string }) {
  return <p className="text-sm text-muted-foreground">{`Session ${n} non terminée.`}</p>
}

/**
 * The counselor manual's page-18 sheet, filled from the API instead of by hand:
 * the all-dimensions table, the RIASEC bars, the ten S0 axes with their tension
 * marks, the sessions 2-5 synthesis boxes and the accroche ingredients.
 *
 * Section values are null when a session is unfinished (contracts § B.5), so
 * every block renders a « non terminée » line rather than assuming.
 *
 * Two things above the table are not the manual's own scoring: the session-0
 * phrase, already shown to the candidate with no human review (phase-4 ruling
 * R6 — marked with `.ai-block`, legend at the top of the sheet), and, when the
 * row was scored under a retired bank version, a sober warning that some
 * sections may look incomplete for a reason unrelated to the person's answers
 * (ruling R10).
 *
 * COUNSELOR SURFACE ONLY (spec decision 7): scores, trait names and framework
 * names appear here and nowhere else in the app.
 */
export function SynthesisSheet({
  synthesis,
  microPhrase,
  microStatus,
  rowScoringVersion,
}: {
  synthesis: VoyageSynthesis
  microPhrase: string | null
  microStatus: MicroStatus
  rowScoringVersion: string
}) {
  const { s0, riasec, s2, s3, s4, s5 } = synthesis

  const highLevel = (level: string) =>
    s3 ? BIG5_ROWS.filter((r) => s3.levels[r.key] === level).map((r) => big5Label(r.key)) : []

  const rows: { dimension: string; session: string; resultat: string; signal: string }[] = [
    {
      dimension: "Axes bipolaires (S0)",
      session: "Session 0",
      resultat: s0 ? join(s0.top3.map((t) => t.label), " / ") : DASH,
      signal: s0 ? `Tensions : ${s0.tensions.length}` : DASH,
    },
    {
      dimension: "RIASEC top 3",
      session: "Session 1",
      resultat: riasec ? riasec.top3.map((t) => `${t.univers} ${t.score}`).join(" / ") : DASH,
      signal: riasec ? `Combinaison : ${riasec.top3.map((t) => t.letter).join("")}` : DASH,
    },
    {
      dimension: "Valeurs Schwartz",
      session: "Session 2",
      resultat: s2 ? join(s2.schwartz_dominant.map((k) => SCHWARTZ_LABELS[k] ?? k)) : DASH,
      signal: s2
        ? `Secondaire : ${join(
            secondary(s2.schwartz, s2.schwartz_dominant).map((k) => SCHWARTZ_LABELS[k] ?? k),
          )}`
        : DASH,
    },
    {
      dimension: "Besoin SDT dominant",
      session: "Session 2",
      resultat: s2 ? join(s2.sdt_dominant.map(sdtLabel)) : DASH,
      signal:
        s2 && s2.sdt_dominant.length > 0
          ? `Score : ${s2.sdt[s2.sdt_dominant[0]] ?? 0}`
          : DASH,
    },
    {
      dimension: "Big Five dominant",
      session: "Session 3",
      resultat: s3 ? `Traits élevés : ${join(highLevel(LEVEL_HIGH), ", ")}` : DASH,
      signal: s3 ? `Traits faibles : ${join(highLevel(LEVEL_LOW), ", ")}` : DASH,
    },
    {
      dimension: "Style cognitif",
      session: "Session 3",
      resultat: s3 ? join(s3.style_dominant.map((k) => STYLE_LABELS[k] ?? k)) : DASH,
      signal: s3 ? s3.intro_extra : DASH,
    },
    {
      dimension: "Profil sensoriel",
      session: "Session 4",
      resultat: s4 ? join([s4.espace, s4.rythme, s4.equipe]) : DASH,
      signal: s4 ? `Irritant : ${s4.irritant}` : DASH,
    },
    {
      dimension: "Appétence risque",
      session: "Session 5",
      resultat: s5 ? s5.risque : DASH,
      signal: s5 ? join([s5.rapport_echec, s5.rapport_flou]) : DASH,
    },
    {
      dimension: "Valeur centrale",
      session: "Session 5",
      resultat: s5 ? s5.valeur_centrale : DASH,
      signal: DASH,
    },
    {
      dimension: "Type d'impact",
      session: "Session 5",
      resultat: s5 ? s5.trace : DASH,
      signal: s5 ? `Sacrifice : ${s5.sacrifice}` : DASH,
    },
    {
      dimension: "Sens — Moment vivant",
      session: "Session 5",
      resultat: s5 ? s5.vivant : DASH,
      signal: DASH,
    },
  ]

  return (
    <div>
      <h2 className="eyebrow text-orange-dark">Synthèse · vue d’ensemble</h2>
      <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{AI_LEGEND}</p>

      <div className="ai-block mt-4 rounded-md p-4">
        <p className="eyebrow text-orange-dark">{PHRASE_MARKER}</p>
        <p className="mt-1.5 text-sm font-medium text-navy">
          {microStatus === "success" ? microPhrase : PHRASE_FALLBACK}
        </p>
      </div>

      {rowScoringVersion !== synthesis.scoring_version ? (
        <p className="mt-4 rounded-lg border border-orange/30 bg-orange/5 px-4 py-3 text-xs leading-relaxed text-navy">
          {STALE_WARNING}
        </p>
      ) : null}

      <Block title="Tableau de synthèse — Toutes dimensions">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[32rem] text-left text-xs">
            <thead>
              <tr className="border-b border-border">
                <th className="eyebrow py-1 pr-2 text-muted-foreground">Dimension</th>
                <th className="eyebrow py-1 pr-2 text-muted-foreground">Session</th>
                <th className="eyebrow py-1 pr-2 text-muted-foreground">Résultat</th>
                <th className="eyebrow py-1 text-muted-foreground">Signal fort ?</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.dimension} className="border-b border-border/60 align-top">
                  <td className="py-1.5 pr-2 font-medium text-navy">{r.dimension}</td>
                  <td className="py-1.5 pr-2 text-muted-foreground">{r.session}</td>
                  <td className="py-1.5 pr-2 text-navy">{r.resultat}</td>
                  <td className="py-1.5 text-muted-foreground">{r.signal}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Block>

      <Block title="Profil RIASEC — Barres de visualisation">
        {riasec ? <RiasecBars riasec={riasec} /> : <Missing n="1" />}
      </Block>

      <Block
        title="Axes bipolaires — Session 0"
        subtitle={"Résultante = OUI moins NON sur les affirmations qui chargent l'axe."}
      >
        {s0 ? (
          <ul className="space-y-1.5">
            {AXIS_ROWS.map(({ id, label, neg, pos }) => {
              const axis = s0.axes[id]
              return (
                <li
                  key={id}
                  className="grid grid-cols-[1.75rem_1fr_auto] items-center gap-2 border-b border-border/50 pb-1.5 last:border-0"
                >
                  <span className="font-mono text-[11px] text-muted-foreground">{id}</span>
                  <div className="min-w-0">
                    <p className="truncate text-xs font-medium text-navy">{label}</p>
                    <p className="truncate text-[11px] text-muted-foreground">
                      {`${neg} ← → ${pos}`}
                    </p>
                  </div>
                  <div className="flex items-center justify-end gap-2">
                    <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
                      {axis ? `${axis.oui} ✓ / ${axis.non} ✗` : DASH}
                    </span>
                    <span
                      className={cn(
                        "w-8 text-right font-mono text-xs font-bold tabular-nums",
                        axis?.tension ? "text-orange-dark" : "text-navy",
                      )}
                    >
                      {axis ? signed(axis.resultant) : DASH}
                    </span>
                    {axis?.tension ? (
                      <Badge variant="warning">tension</Badge>
                    ) : (
                      <span className="w-[4.25rem]" aria-hidden="true" />
                    )}
                  </div>
                </li>
              )
            })}
          </ul>
        ) : (
          <Missing n="0" />
        )}
      </Block>

      <Block
        title="Tensions S0 — Ambivalences à explorer"
        subtitle="Les tensions (score S0 entre −2 et +2) sont les signaux les plus informatifs. Elles pondèrent ×1.5 le portrait."
      >
        {!s0 ? (
          <Missing n="0" />
        ) : s0.tensions.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucune tension relevée.</p>
        ) : (
          <ul className="space-y-2">
            {s0.tensions.map((t) => (
              <li key={t.axis} className="rounded-md bg-secondary p-3">
                <p className="text-xs font-semibold text-navy">
                  {t.label}{" "}
                  <span className="font-mono font-normal text-muted-foreground">
                    ({t.axis} · {signed(t.resultant)})
                  </span>
                </p>
                {/* The question is the restitution guide's own phase-03 line,
                    with this axis dropped into the manual's [axe] slot. */}
                <p className="mt-1 text-xs italic text-muted-foreground">
                  {`« J'ai noté une ambivalence sur ${t.tension}. Tu as autant coché des deux côtés. Qu'est-ce que ça t'évoque ? »`}
                </p>
              </li>
            ))}
          </ul>
        )}
      </Block>

      <Block title="Synthèse — Besoins SDT dominants">
        {s2 ? (
          <div className="space-y-3">
            <div className="grid grid-cols-3 gap-3">
              {SDT_ROWS.map(({ key, label }) => (
                <div
                  key={key}
                  className={cn(
                    "rounded-md p-3 text-center",
                    s2.sdt_dominant.includes(key) ? "bg-peach-soft" : "bg-secondary",
                  )}
                >
                  <p className="text-xs font-semibold text-navy">{label}</p>
                  <p className="mt-1 font-mono text-lg font-bold tabular-nums text-navy">
                    {s2.sdt[key] ?? 0}
                  </p>
                </div>
              ))}
            </div>
            <Field
              label={"Valeur centrale dominante (Schwartz) du jeune"}
              value={join(s2.schwartz_dominant.map((k) => SCHWARTZ_LABELS[k] ?? k))}
            />
            <Field
              label="Valeurs secondaires"
              value={join(
                secondary(s2.schwartz, s2.schwartz_dominant).map((k) => SCHWARTZ_LABELS[k] ?? k),
              )}
            />
            <Field
              label={"Ambivalences identifiées (S2-7) — à explorer en restitution"}
              value={`${s2.ambivalences.label} — ${s2.ambivalences.plain}`}
            />
          </div>
        ) : (
          <Missing n="2" />
        )}
      </Block>

      <Block title="Synthèse Big Five — Profil cognitif">
        {s3 ? (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
              {BIG5_ROWS.map(({ key, label }) => (
                <div key={key} className="rounded-md bg-secondary p-2 text-center">
                  <p className="text-[11px] font-medium text-muted-foreground">{label}</p>
                  <p className="mt-0.5 text-sm font-semibold text-navy">
                    {s3.levels[key] ?? DASH}
                  </p>
                  <p className="font-mono text-[11px] tabular-nums text-muted-foreground">
                    {signed(s3.big5[key] ?? 0)}
                  </p>
                </div>
              ))}
            </div>
            <Field
              label={"Style cognitif dominant (holistique / séquentiel / adaptatif / consultatif)"}
              value={join(s3.style_dominant.map((k) => STYLE_LABELS[k] ?? k))}
            />
            <Field
              label={"Signaux d'introversion / extraversion à noter pour la restitution"}
              value={s3.intro_extra}
            />
          </div>
        ) : (
          <Missing n="3" />
        )}
      </Block>

      <Block title="Synthèse environnementale">
        {s4 ? (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {S4_ROWS.map(({ key, label }) => (
              <Field key={key} label={label} value={s4[key]} />
            ))}
          </div>
        ) : (
          <Missing n="4" />
        )}
      </Block>

      <Block title="Synthèse Risque & Sens">
        {s5 ? (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {S5_ROWS.map(({ key, label }) => (
              <Field key={key} label={label} value={s5[key]} />
            ))}
          </div>
        ) : (
          <Missing n="5" />
        )}
      </Block>

      <Block
        title={"Phrase d'accroche provisoire du portrait"}
        subtitle={"1 phrase — cf. top 3 axes + S5-7"}
      >
        <div className="space-y-3">
          <Field
            label="Top 3 axes"
            value={s0 ? join(s0.top3.map((t) => t.label)) : DASH}
          />
          <Field label={"Se sent vivant(e) quand"} value={s5 ? s5.vivant : DASH} />
        </div>
      </Block>
    </div>
  )
}

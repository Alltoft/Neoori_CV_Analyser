"use client"

import { OptionCard } from "@/components/voyage/OptionCard"
import { RANK_MAX, type BankScene } from "@/types/voyage"

/**
 * One scene, one screen. Title, subtitle, narrative, question and options are
 * the cahier's own text (tutoiement), served by GET /api/voyage/bank and
 * rendered verbatim — spec decision 15.
 *
 * Up to RANK_MAX options, in preference order: a tap adds the option as the
 * next choice, a second tap removes it and moves the later ones up. The server
 * shares the scene's one vote between them, first choice heaviest
 * (scoring.rank_weights) — the person sees the order, never a weight.
 */
export function SceneCard({
  scene,
  value,
  disabled,
  onChange,
}: {
  scene: BankScene
  /** The chosen letters, first choice first. */
  value: string[]
  disabled?: boolean
  onChange: (letters: string[]) => void
}) {
  const full = value.length >= RANK_MAX

  const toggle = (letter: string) => {
    if (value.includes(letter)) onChange(value.filter((l) => l !== letter))
    else if (!full) onChange([...value, letter])
  }

  return (
    <article className="overflow-hidden rounded-2xl bg-card shadow-soft ring-1 ring-foreground/10">
      <div className="voyage-rule" />
      <div className="p-5 sm:p-6">
        <h2 className="font-display text-xl font-bold leading-tight text-navy">{scene.title}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{scene.subtitle}</p>

        {scene.narrative.length > 0 && (
          <div className="mt-4 space-y-2.5 rounded-xl bg-secondary/60 p-4">
            {scene.narrative.map((paragraph, i) => (
              <p key={i} className="text-sm leading-relaxed text-navy-700">{paragraph}</p>
            ))}
          </div>
        )}

        <p className="mt-5 font-display text-base font-semibold text-navy">{scene.question}</p>
        <p aria-live="polite" className="mt-1 text-xs text-muted-foreground">
          {full && !disabled
            ? `${RANK_MAX} choix au maximum : retire un choix pour en changer.`
            : `Choisis d'abord ce qui te correspond le mieux. Tu peux ajouter d'autres choix, par ordre de préférence (${RANK_MAX} au maximum).`}
        </p>

        <div className="mt-3 space-y-2">
          {scene.options.map((o) => {
            const at = value.indexOf(o.letter)
            return (
              <OptionCard
                key={o.letter}
                letter={o.letter}
                label={o.label}
                text={o.text}
                rank={at === -1 ? undefined : at + 1}
                disabled={disabled || (full && at === -1)}
                onSelect={() => toggle(o.letter)}
              />
            )
          })}
        </div>
      </div>
    </article>
  )
}

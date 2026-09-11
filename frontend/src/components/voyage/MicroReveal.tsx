"use client"

import { LoaderCircle, Sparkles } from "lucide-react"

import { Button } from "@/components/ui/button"
import type { MicroStatus } from "@/types/voyage"

/**
 * The one sentence session 0 produces — the whole of what S0 gives back, since
 * the candidate never sees a score, a trait name or a framework name.
 *
 * Label: « Votre phrase ». The prompt-side wording (« Phrase révélée ») shares a
 * root with a banned word and never appears in the UI.
 *
 * A failed or stalled generation is retryable (PM-Q2): the candidate is never
 * shown a failure reason, only that nothing has arrived yet and a way to ask
 * again. `stalled` covers both a `generating` row past the hub's polling
 * ceiling and a plain `error` row — both get the same "Réessayer" button.
 */
export function MicroReveal({
  status,
  phrase,
  stalled,
  retrying,
  onRetry,
}: {
  status: MicroStatus
  phrase: string | null
  stalled: boolean
  retrying: boolean
  onRetry: () => void
}) {
  if (status === "none") return null

  const showRetry = status === "error" || (status === "generating" && stalled)

  return (
    <div className="overflow-hidden rounded-2xl bg-navy shadow-card">
      <div className="voyage-rule" />
      <div className="px-5 py-5 sm:px-6">
        <p className="eyebrow inline-flex items-center gap-2 text-peach">
          <Sparkles className="size-3.5" aria-hidden /> Votre phrase
        </p>

        {status === "generating" && !stalled && (
          <p className="mt-3 inline-flex items-center gap-2 text-sm text-white/80">
            <LoaderCircle className="size-4 animate-spin" aria-hidden />
            Nous la rédigeons. Quelques secondes.
          </p>
        )}

        {status === "generating" && stalled && (
          <p className="mt-3 text-sm text-white/80">
            La rédaction de votre phrase prend plus de temps que prévu. Vos réponses sont
            enregistrées.
          </p>
        )}

        {status === "success" && phrase && (
          <p className="mt-3 font-display text-lg leading-relaxed text-white">{phrase}</p>
        )}

        {status === "error" && (
          <p className="mt-3 text-sm text-white/80">
            La rédaction de votre phrase n&apos;a pas abouti. Vos réponses sont enregistrées.
          </p>
        )}

        {showRetry && (
          <Button
            size="sm"
            disabled={retrying}
            onClick={onRetry}
            className="mt-3 bg-white text-navy hover:bg-white/90"
          >
            {retrying ? "Relance…" : "Réessayer"}
          </Button>
        )}
      </div>
    </div>
  )
}

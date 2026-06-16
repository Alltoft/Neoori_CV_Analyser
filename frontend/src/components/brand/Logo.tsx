import { cn } from "@/lib/utils"

type Tone = "navy" | "light"

/**
 * neoori infinity mark — two overlapping rings forming the "oo".
 * Orange→peach gradient. Optional stroke-draw on mount (reduced-motion safe).
 */
function InfinityMark({
  animate = false,
  className,
  style,
}: {
  animate?: boolean
  className?: string
  style?: React.CSSProperties
}) {
  // circumference of r=14.5 ≈ 91.1 — used for the draw animation
  const C = 91.1
  const drawL = { strokeDasharray: C, strokeDashoffset: C } as const

  // Solid stroke colors (NO gradient/id/var) so the mark renders reliably
  // everywhere — including print/PDF and on navy bands.
  return (
    <svg
      viewBox="0 0 64 38"
      fill="none"
      aria-hidden="true"
      className={className}
      style={{ height: "0.66em", width: "auto", ...style }}
    >
      <circle
        cx="19" cy="19" r="14.5"
        stroke="#ea5624" strokeWidth="5"
        style={animate ? { ...drawL, animation: "neo-draw 1s cubic-bezier(0.65,0,0.35,1) 0.1s forwards" } : undefined}
      />
      <circle
        cx="45" cy="19" r="14.5"
        stroke="#f7ae78" strokeWidth="5"
        style={animate ? { ...drawL, animation: "neo-draw 1s cubic-bezier(0.65,0,0.35,1) 0.3s forwards" } : undefined}
      />
    </svg>
  )
}

export function Logo({
  variant = "full",
  tone = "navy",
  animate = false,
  className,
}: {
  variant?: "full" | "mark"
  tone?: Tone
  animate?: boolean
  className?: string
}) {
  if (variant === "mark") {
    return <InfinityMark animate={animate} className={className} style={{ height: "1em" }} />
  }

  return (
    <span
      className={cn(
        "inline-flex items-center font-display font-extrabold lowercase leading-none tracking-tight select-none",
        tone === "light" ? "text-white" : "text-navy",
        className,
      )}
    >
      <span>ne</span>
      <InfinityMark animate={animate} className="mx-[0.03em]" />
      <span>ri</span>
    </span>
  )
}

export { InfinityMark }

import { useId } from "react"
import { cn } from "@/lib/utils"
import {
  LOGO_LETTERS, LOGO_NAVY, LOGO_OO, LOGO_OO_GRADIENT, LOGO_VIEWBOX,
  MARK_GRADIENT, MARK_PATH, MARK_VIEWBOX,
} from "./logo-paths"

/* The neoori logo, drawn from the vector files in public/brand/ (landings
   spec, decision 27): one line and no tagline, so every visible word is
   French. Size it with font-size: the wordmark is 1.05em tall, about the
   width the old two-line PNG had. On dark surfaces (`tone="light"` /
   `onDark`) the letters turn white and the oo keeps its gradient; there is
   no white plate any more. The SVG ring/figure marks further down are brand
   MOTIFS (decorative accents that echo the oo), not the logo. */

type Tone = "navy" | "light"

export function Logo({
  variant = "full",
  tone = "navy",
  onDark,
  className,
}: {
  variant?: "full" | "mark" | "wordmark"
  tone?: Tone
  onDark?: boolean
  /** Legacy no-op: the logo is inline SVG, nothing to preload. */
  priority?: boolean
  className?: string
  /** Legacy no-op, kept for back-compat. */
  animate?: boolean
}) {
  // One gradient per logo: two logos on a page (AuthLayout has two) must not
  // share an id, or hiding the first would blank the second's gradient.
  const id = `lg${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`

  if (variant === "mark") {
    return (
      <svg
        viewBox={`0 0 ${MARK_VIEWBOX.w} ${MARK_VIEWBOX.h}`}
        role="img"
        aria-label="neoori"
        className={cn("inline-block shrink-0 select-none", className)}
        style={{ height: "1em", width: "auto" }}
      >
        <defs>
          <linearGradient id={id} x1={MARK_GRADIENT.x1} y1="0" x2={MARK_GRADIENT.x2} y2="0" gradientUnits="userSpaceOnUse">
            {MARK_GRADIENT.stops.map(([offset, color]) => <stop key={offset} offset={offset} stopColor={color} />)}
          </linearGradient>
        </defs>
        <path d={MARK_PATH} fill={`url(#${id})`} />
      </svg>
    )
  }

  const light = onDark ?? tone === "light"
  return (
    <svg
      viewBox={`0 0 ${LOGO_VIEWBOX.w} ${LOGO_VIEWBOX.h}`}
      role="img"
      aria-label="neoori"
      className={cn("inline-block shrink-0 select-none", className)}
      style={{ height: "1.05em", width: "auto" }}
    >
      <defs>
        <linearGradient id={id} x1={LOGO_OO_GRADIENT.x1} y1="0" x2={LOGO_OO_GRADIENT.x2} y2="0" gradientUnits="userSpaceOnUse">
          {LOGO_OO_GRADIENT.stops.map(([offset, color]) => <stop key={offset} offset={offset} stopColor={color} />)}
        </linearGradient>
      </defs>
      <g fill={light ? "#ffffff" : LOGO_NAVY}>
        <path d={LOGO_LETTERS.n} />
        <path d={LOGO_LETTERS.e} />
        <path d={LOGO_LETTERS.r} />
        <path d={LOGO_LETTERS.i} />
      </g>
      <path d={LOGO_OO} fill={`url(#${id})`} />
    </svg>
  )
}

/* ── Brand motif: the interlocking "oo" / ∞ rings (orange + navy). ──
   Signature device for parcours→avenir, section markers and the loading moment.
   Solid strokes (print-safe), optional draw-on-mount. */
const ORANGE = "#ea5624"
const NAVY_RING = "#234279"

export function InfinityMark({
  tone = "navy",
  animate = false,
  className,
  style,
}: {
  tone?: Tone
  animate?: boolean
  className?: string
  style?: React.CSSProperties
}) {
  const C = 91.1 // circumference of r=14.5 for the draw animation
  const drawL = { strokeDasharray: C, strokeDashoffset: C } as const
  const ringTwo = tone === "light" ? "#ffffff" : NAVY_RING

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
        stroke={ORANGE} strokeWidth="5"
        style={animate ? { ...drawL, animation: "neo-draw 1s cubic-bezier(0.65,0,0.35,1) 0.1s forwards" } : undefined}
      />
      <circle
        cx="45" cy="19" r="14.5"
        stroke={ringTwo} strokeWidth="5"
        style={animate ? { ...drawL, animation: "neo-draw 1s cubic-bezier(0.65,0,0.35,1) 0.3s forwards" } : undefined}
      />
    </svg>
  )
}

/* Legacy figure mark kept only as a faint ambient motif (NOT used as the logo). */
export function BrandMark({
  tone = "navy",
  className,
  style,
}: {
  tone?: Tone
  className?: string
  style?: React.CSSProperties
}) {
  const base = tone === "light" ? "#fbd9c6" : "#1c3561"
  return (
    <svg viewBox="0 0 96 100" fill="none" aria-hidden="true" className={className} style={{ height: "1em", width: "auto", ...style }}>
      <path d="M14,78 C10,67 23,59 33,63 C43,67 45,82 35,90 C26,97 17,90 14,78 Z" fill={base} />
      <path d="M58,8 C79,20 85,46 66,66 C56,77 40,80 28,72 C41,60 38,29 58,8 Z" fill="#ea5624" />
      <path d="M58,8 C79,20 85,46 66,66 C72,45 65,24 49,14 C52,11 55,9 58,8 Z" fill="#f4a276" />
      <circle cx="33" cy="17" r="12" fill="#ef7d4b" />
    </svg>
  )
}

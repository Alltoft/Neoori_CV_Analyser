import Image from "next/image"
import { cn } from "@/lib/utils"

/* The official neoori logo is the raster lockup shipped in /public — used verbatim,
   never recolored. On dark surfaces it sits on a white "clear-space" plate so the
   artwork itself stays untouched. The SVG ring/figure marks below are brand MOTIFS
   (decorative accents that echo the logo's "oo" rings), not the logo. */

const LOGO_SRC = "/neoori-logo.png"      // exact brand lockup, 1527×486
const MARK_SRC = "/img/neoori-mark.png"  // optional square figure glyph, 512×512

type Tone = "navy" | "light"

/**
 * neoori logo. Sizing is font-relative: the artwork renders at `1em` tall, so set
 * the size with a text-* class (e.g. `className="text-2xl"`) on the Logo or a parent.
 * `tone="light"` / `onDark` seats it on a white plate for navy/photo backgrounds.
 */
export function Logo({
  variant = "full",
  tone = "navy",
  onDark,
  priority = false,
  className,
  animate: _animate, // legacy no-op (kept for back-compat)
}: {
  variant?: "full" | "mark" | "wordmark"
  tone?: Tone
  onDark?: boolean
  priority?: boolean
  className?: string
  animate?: boolean
}) {
  const dark = onDark ?? tone === "light"
  const isMark = variant === "mark"
  const src = isMark ? MARK_SRC : LOGO_SRC
  const w = isMark ? 512 : 1527
  const h = isMark ? 512 : 486

  const img = (
    <Image
      src={src}
      alt="neoori"
      width={w}
      height={h}
      priority={priority}
      sizes="260px"
      quality={92}
      className={cn("select-none", !dark && className)}
      style={{ height: "1em", width: "auto" }}
    />
  )

  if (dark) {
    return (
      <span
        className={cn(
          "inline-flex items-center rounded-[0.5em] bg-white px-[0.5em] py-[0.32em] shadow-sm ring-1 ring-black/5",
          className,
        )}
      >
        {img}
      </span>
    )
  }
  return img
}

/* ── Brand motif: the interlocking "oo" / ∞ rings (orange + navy). ──
   Signature device for parcours→avenir, section markers and the loading moment.
   Solid strokes (print-safe), optional draw-on-mount. */
const ORANGE = "#ff7a39"
const NAVY_RING = "#15386d"

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
  const base = tone === "light" ? "#ffd9bf" : "#0f1e34"
  return (
    <svg viewBox="0 0 96 100" fill="none" aria-hidden="true" className={className} style={{ height: "1em", width: "auto", ...style }}>
      <path d="M14,78 C10,67 23,59 33,63 C43,67 45,82 35,90 C26,97 17,90 14,78 Z" fill={base} />
      <path d="M58,8 C79,20 85,46 66,66 C56,77 40,80 28,72 C41,60 38,29 58,8 Z" fill="#ff7a39" />
      <path d="M58,8 C79,20 85,46 66,66 C72,45 65,24 49,14 C52,11 55,9 58,8 Z" fill="#ffb877" />
      <circle cx="33" cy="17" r="12" fill="#ff9a4d" />
    </svg>
  )
}

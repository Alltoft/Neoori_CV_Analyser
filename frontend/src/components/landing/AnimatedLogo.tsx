"use client"

import { useEffect, useId, useRef } from "react"
import {
  LOGO_LETTERS, LOGO_NAVY, LOGO_OO, LOGO_OO_GRADIENT, LOGO_VIEWBOX,
} from "@/components/brand/logo-paths"
import { shouldPlayLogo } from "@/lib/logo-motion"

const MID = 47.24 // radius of the oo's mid-circle, in logo units
const C = 2 * Math.PI * MID
const RINGS = [
  { cx: 323.97, rotate: -90 }, // the left ring starts at 12 o'clock
  { cx: 418.45, rotate: 90 }, // the right ring starts at 6 o'clock
] as const

/** The logo with motion A, « Tracé » (landings spec, decision 19): the two
 *  rings draw, then n·e·r·i rise. Once per tab session, never under reduce
 *  motion. The resting state is the plain logo, so nothing is hidden when
 *  JavaScript is off or the motion is skipped. */
export function AnimatedLogo({ tone = "navy", className }: { tone?: "navy" | "light"; className?: string }) {
  const id = `alg${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`
  const ref = useRef<SVGSVGElement>(null)
  // Decided once per mounted logo. shouldPlayLogo() marks the tab session at
  // once, so an effect that runs again on the same logo — React's Strict Mode
  // does it in development, after cancelling the first run's animations —
  // must replay the decision, not ask again.
  const plays = useRef<boolean | null>(null)

  useEffect(() => {
    const svg = ref.current
    if (!svg) return
    if (plays.current === null) {
      let storage: Storage | null = null
      try {
        storage = window.sessionStorage
      } catch {
        storage = null
      }
      const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches
      plays.current = shouldPlayLogo(storage, reduced)
    }
    if (!plays.current) return
    const draw = [{ strokeDashoffset: `${C}px` }, { strokeDashoffset: "0px" }]
    const animations: Animation[] = []
    svg.querySelectorAll<SVGCircleElement>("[data-ring]").forEach((ring, i) => {
      animations.push(ring.animate(draw, { duration: 900, delay: i * 160, easing: "cubic-bezier(.65,0,.35,1)", fill: "both" }))
    })
    svg.querySelectorAll<SVGPathElement>("[data-letter]").forEach((letter, i) => {
      animations.push(letter.animate(
        [{ transform: "translateY(28px)", opacity: 0 }, { transform: "none", opacity: 1 }],
        { duration: 620, delay: 560 + i * 70, easing: "cubic-bezier(.16,1,.3,1)", fill: "both" },
      ))
    })
    return () => animations.forEach((a) => a.cancel())
  }, [])

  return (
    <svg ref={ref} viewBox={`0 0 ${LOGO_VIEWBOX.w} ${LOGO_VIEWBOX.h}`} role="img" aria-label="neoori" className={className}>
      <defs>
        <linearGradient id={`${id}-g`} x1={LOGO_OO_GRADIENT.x1} y1="0" x2={LOGO_OO_GRADIENT.x2} y2="0" gradientUnits="userSpaceOnUse">
          {LOGO_OO_GRADIENT.stops.map(([offset, color]) => <stop key={offset} offset={offset} stopColor={color} />)}
        </linearGradient>
        <mask id={`${id}-m`} maskUnits="userSpaceOnUse" x="0" y="-40" width={LOGO_VIEWBOX.w} height="260">
          {RINGS.map((ring) => (
            <circle
              key={ring.cx}
              data-ring=""
              cx={ring.cx}
              cy="108.21"
              r={MID}
              fill="none"
              stroke="#fff"
              strokeWidth="44"
              strokeDasharray={`${C} ${C}`}
              strokeDashoffset="0"
              transform={`rotate(${ring.rotate} ${ring.cx} 108.21)`}
            />
          ))}
        </mask>
      </defs>
      <g fill={tone === "light" ? "#ffffff" : LOGO_NAVY}>
        {(["n", "e", "r", "i"] as const).map((key) => (
          <path key={key} data-letter="" d={LOGO_LETTERS[key]} style={{ transformBox: "view-box" }} />
        ))}
      </g>
      <path d={LOGO_OO} fill={`url(#${id}-g)`} mask={`url(#${id}-m)`} />
    </svg>
  )
}

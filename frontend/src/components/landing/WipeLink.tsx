"use client"

import type { MouseEvent, ReactNode } from "react"
import { useRouter } from "next/navigation"
import { AppLink, useSite } from "@/lib/site-context"
import { waitForNavigation } from "@/lib/nav-settle"
import { ringSnapshot, wipeRadius } from "@/lib/wipe"

const RING = { orange: "#ea5624", peach: "#f7b394" } as const
const VARS = ["--wipe-x", "--wipe-y", "--wipe-r", "--ring-tx", "--ring-ty", "--ring-scale"] as const

/** The landing's main button, with the ∞ wipe (landings spec, decision 22):
 *  the next page appears in a circle growing from the button, a thin brand
 *  ring riding its edge. A plain link without JavaScript or View Transitions,
 *  under reduce motion, with a modifier key, or towards another host. */
export function WipeLink({
  href,
  ring,
  className,
  children,
}: {
  href: string
  ring: keyof typeof RING
  className?: string
  children: ReactNode
}) {
  const router = useRouter()
  const site = useSite()

  const onClick = (event: MouseEvent<HTMLAnchorElement>) => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
    if (site.href(href) !== href) return
    if (typeof document.startViewTransition !== "function") return
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return
    event.preventDefault()

    // A keyboard press has no pointer position: open from the button's centre.
    const box = event.currentTarget.getBoundingClientRect()
    const x = event.detail > 0 ? event.clientX : box.left + box.width / 2
    const y = event.detail > 0 ? event.clientY : box.top + box.height / 2
    const radius = wipeRadius(x, y, window.innerWidth, window.innerHeight)
    const snap = ringSnapshot(radius)
    const root = document.documentElement
    root.style.setProperty("--wipe-x", `${x}px`)
    root.style.setProperty("--wipe-y", `${y}px`)
    root.style.setProperty("--wipe-r", `${radius}px`)
    root.style.setProperty("--ring-tx", `${x - snap.size / 2}px`)
    root.style.setProperty("--ring-ty", `${y - snap.size / 2}px`)
    root.style.setProperty("--ring-scale", String(snap.scale))
    root.classList.add("neoori-wipe")
    const ringElement = drawRing(snap, RING[ring])

    const transition = document.startViewTransition(async () => {
      ringElement.remove()
      router.push(href)
      await waitForNavigation()
    })
    transition.ready.catch(() => {})
    transition.finished
      .finally(() => {
        ringElement.remove()
        root.classList.remove("neoori-wipe")
        for (const name of VARS) root.style.removeProperty(name)
      })
      .catch(() => {})
  }

  return (
    <AppLink href={href} className={className} onClick={onClick}>
      {children}
    </AppLink>
  )
}

/** The ring, drawn at its snapshot size just off the left edge of the
 *  screen: the visitor never sees it before it grows, and Chrome captures it
 *  at full size, so it stays sharp. (Scaled down in place instead, Chrome
 *  captured it at its on-screen size, a few pixels, and the ring vanished.)
 *  The keyframes place it at the click. It leaves the DOM in the
 *  transition's update, so it exists only in the old state. */
function drawRing(snap: { size: number; stroke: number }, color: string): SVGSVGElement {
  const ns = "http://www.w3.org/2000/svg"
  const { size, stroke } = snap
  const svg = document.createElementNS(ns, "svg")
  svg.setAttribute("width", String(size))
  svg.setAttribute("height", String(size))
  svg.setAttribute("viewBox", `0 0 ${size} ${size}`)
  svg.setAttribute("aria-hidden", "true")
  svg.style.cssText = [
    "position:fixed",
    `left:${-size - 64}px`,
    "top:0",
    `width:${size}px`,
    `height:${size}px`,
    "pointer-events:none",
    "view-transition-name:neoori-wipe-ring",
    "z-index:2147483647",
  ].join(";")
  const circle = document.createElementNS(ns, "circle")
  circle.setAttribute("cx", String(size / 2))
  circle.setAttribute("cy", String(size / 2))
  circle.setAttribute("r", String(size / 2 - stroke / 2))
  circle.setAttribute("fill", "none")
  circle.setAttribute("stroke", color)
  circle.setAttribute("stroke-width", String(stroke))
  svg.appendChild(circle)
  document.body.appendChild(svg)
  return svg
}

"use client"

import { useState } from "react"
import { renderStill, type SceneKind } from "@/components/landing/scenes"
import type { Layout } from "@/components/landing/scenes/core"
import { LOGO_LETTERS, LOGO_NAVY, LOGO_OO, LOGO_OO_GRADIENT, LOGO_VIEWBOX } from "@/components/brand/logo-paths"
import { cvCopy } from "@/components/landing/copy/cv"
import { voyageCopy } from "@/components/landing/copy/voyage"

interface StillSpec {
  name: string
  scene: SceneKind
  layout: Layout
  width: number
  height: number
  pixelRatio: number
}

// CSS sizes of the boxes the landings give each still: the cv. desktop box is
// 620 × 694 at most (aspect 1 / 1.12); the voyage. desktop box is 72 % of a
// 1440 px hero (1037 px, square); the phone boxes at 390 px wide.
const STILLS: StillSpec[] = [
  { name: "cv-desktop", scene: "sheet", layout: "desktop", width: 620, height: 694, pixelRatio: 2 },
  { name: "cv-phone", scene: "sheet", layout: "phone", width: 390, height: 335, pixelRatio: 2 },
  { name: "voyage-desktop", scene: "mark", layout: "desktop", width: 1037, height: 1037, pixelRatio: 1.5 },
  { name: "voyage-phone", scene: "mark", layout: "phone", width: 390, height: 300, pixelRatio: 2 },
]

async function save(name: string, canvas: HTMLCanvasElement): Promise<string> {
  const blob = await new Promise<Blob>((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error(`${name}: empty canvas`))), "image/png"))
  const response = await fetch(`/dev/stills/save?name=${encodeURIComponent(`${name}.png`)}`, { method: "POST", body: blob })
  if (!response.ok) throw new Error(`${name}: ${response.status} ${await response.text()}`)
  const { saved } = (await response.json()) as { saved: string }
  return saved
}

function logoImage(light: boolean): Promise<HTMLImageElement> {
  const stops = LOGO_OO_GRADIENT.stops.map(([offset, color]) => `<stop offset="${offset}" stop-color="${color}"/>`).join("")
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${LOGO_VIEWBOX.w} ${LOGO_VIEWBOX.h}">` +
    `<defs><linearGradient id="g" x1="${LOGO_OO_GRADIENT.x1}" y1="0" x2="${LOGO_OO_GRADIENT.x2}" y2="0" gradientUnits="userSpaceOnUse">${stops}</linearGradient></defs>` +
    `<g fill="${light ? "#ffffff" : LOGO_NAVY}">${Object.values(LOGO_LETTERS).map((d) => `<path d="${d}"/>`).join("")}</g>` +
    `<path d="${LOGO_OO}" fill="url(#g)"/></svg>`
  return new Promise((resolve, reject) => {
    const image = new Image()
    image.onload = () => resolve(image)
    image.onerror = () => reject(new Error("logo image"))
    image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
  })
}

function wrap(g: CanvasRenderingContext2D, text: string, maxWidth: number): string[] {
  const lines: string[] = []
  let line = ""
  for (const word of text.split(" ")) {
    const next = line ? `${line} ${word}` : word
    if (line && g.measureText(next).width > maxWidth) {
      lines.push(line)
      line = word
    } else {
      line = next
    }
  }
  if (line) lines.push(line)
  return lines
}

/** A 1200 × 630 share image: the ground, the 3D still on the right, the logo,
 *  the label and the headline (landings spec, decision 15). */
async function shareImage(app: "cv" | "voyage", still: HTMLCanvasElement): Promise<HTMLCanvasElement> {
  const dark = app === "voyage"
  const hero = dark ? voyageCopy.hero : cvCopy.hero
  const canvas = document.createElement("canvas")
  canvas.width = 1200
  canvas.height = 630
  const g = canvas.getContext("2d")
  if (!g) throw new Error("2d context unavailable")
  g.fillStyle = dark ? "#1c3561" : "#f4f6fa"
  g.fillRect(0, 0, 1200, 630)
  const scale = Math.min(540 / still.width, 560 / still.height)
  const w = still.width * scale
  const h = still.height * scale
  g.drawImage(still, 1200 - 48 - w, (630 - h) / 2, w, h)
  g.drawImage(await logoImage(dark), 72, 64, 190, (190 * LOGO_VIEWBOX.h) / LOGO_VIEWBOX.w)

  const css = getComputedStyle(document.documentElement)
  const display = css.getPropertyValue("--font-jakarta").trim() || "sans-serif"
  const mono = css.getPropertyValue("--font-jetbrains").trim() || "monospace"
  await document.fonts.load(`800 54px ${display}`)
  await document.fonts.load(`500 18px ${mono}`)
  const spaced = g as CanvasRenderingContext2D & { letterSpacing: string }
  g.fillStyle = dark ? "#f7b394" : "#c9491e"
  g.font = `500 18px ${mono}`
  spaced.letterSpacing = "3px"
  g.fillText(hero.label.toUpperCase(), 72, 220)
  spaced.letterSpacing = "0px"
  g.fillStyle = dark ? "#ffffff" : "#1c3561"
  g.font = `800 54px ${display}`
  wrap(g, hero.title, 560).forEach((line, i) => g.fillText(line, 72, 296 + i * 62))
  return canvas
}

/** Renders the four stills and the two share images, and saves them. */
export function StillsStudio() {
  const [log, setLog] = useState<string[]>([])
  const [busy, setBusy] = useState(false)

  const run = async () => {
    setBusy(true)
    const lines: string[] = []
    const add = (line: string) => {
      lines.push(line)
      setLog([...lines])
    }
    try {
      const desktop: Partial<Record<"cv" | "voyage", HTMLCanvasElement>> = {}
      for (const spec of STILLS) {
        const { canvas, dispose } = renderStill(spec.scene, spec.layout, spec.width, spec.height, spec.pixelRatio)
        add(`${spec.name}: ${await save(spec.name, canvas)}`)
        if (spec.layout === "desktop") {
          const copy = document.createElement("canvas")
          copy.width = canvas.width
          copy.height = canvas.height
          copy.getContext("2d")?.drawImage(canvas, 0, 0)
          desktop[spec.scene === "sheet" ? "cv" : "voyage"] = copy
        }
        dispose()
      }
      for (const app of ["cv", "voyage"] as const) {
        const still = desktop[app]
        if (!still) throw new Error(`${app}: no desktop still`)
        add(`og-${app}: ${await save(`og-${app}`, await shareImage(app, still))}`)
      }
      add("Terminé. Lancez maintenant : node scripts/encode-stills.mjs")
    } catch (error) {
      add(`Erreur : ${error instanceof Error ? error.message : String(error)}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <main style={{ padding: 32, fontFamily: "system-ui", display: "grid", gap: 16, maxWidth: 720 }}>
      <h1>Images fixes des landings</h1>
      <p>Rend les quatre images fixes et les deux images de partage depuis les scènes 3D, puis les enregistre dans public/.</p>
      <button type="button" onClick={run} disabled={busy} style={{ justifySelf: "start", padding: "10px 16px" }}>
        {busy ? "Rendu…" : "Rendre et enregistrer"}
      </button>
      <pre>{log.join("\n")}</pre>
    </main>
  )
}

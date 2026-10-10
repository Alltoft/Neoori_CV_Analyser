import { test } from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"

// Landings spec, decision 31: AA contrast (4.5:1 for text this size) on the
// small texts the review measured below it. Colours are read from the
// stylesheet itself, so a later edit cannot slip back under.
const css = readFileSync(new URL("../components/landing/landing.css", import.meta.url), "utf8")
const tokens = new Map([...css.matchAll(/(--lp-[\w-]+):\s*(#[0-9a-f]{6})/gi)].map((m) => [m[1], m[2]]))

function colourOf(selector: string): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
  const rule = css.match(new RegExp(`(?:^|\\n)${escaped} \\{([^}]*)\\}`))
  assert.ok(rule, `no rule for ${selector}`)
  const value = rule[1].match(/(?:^|;)\s*color:\s*([^;]+)/)?.[1].trim()
  assert.ok(value, `no colour in ${selector}`)
  const token = value.match(/^var\((--lp-[\w-]+)\)$/)?.[1]
  return token ? (tokens.get(token) ?? value) : value
}

type Rgb = [number, number, number]

function rgb(colour: string, under: Rgb = [255, 255, 255]): Rgb {
  const hex = colour.match(/^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i)
  if (hex) return [1, 2, 3].map((i) => parseInt(hex[i], 16)) as Rgb
  const rgba = colour.match(/^rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)$/)
  assert.ok(rgba, `unreadable colour ${colour}`)
  const alpha = Number(rgba[4])
  return [1, 2, 3].map((i, k) => Number(rgba[i]) * alpha + under[k] * (1 - alpha)) as Rgb
}

function luminance([r, g, b]: Rgb): number {
  const linear = (c: number) => {
    const s = c / 255
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b)
}

function contrast(text: string, ground: string): number {
  const back = rgb(ground)
  const [a, b] = [luminance(rgb(text, back)), luminance(back)].sort((x, y) => y - x)
  return (a + 0.05) / (b + 0.05)
}

test("small landing texts meet AA contrast (decision 31)", () => {
  const cases: [string, string, string][] = [
    ["§ numbers on a white tier card", colourOf(".lp-tier li b"), "#ffffff"],
    ["§ numbers on the phone's cool band", colourOf(".lp-tier li b"), tokens.get("--lp-cool") ?? ""],
    ["step numbers on peach-soft", colourOf(".lp-steps > li::before"), tokens.get("--lp-peach-soft") ?? ""],
    ["the footer's © line on navy", colourOf(".lp-footer-copy"), tokens.get("--lp-navy") ?? ""],
  ]
  for (const [what, text, ground] of cases) {
    const ratio = contrast(text, ground)
    assert.ok(ratio >= 4.5, `${what}: ${ratio.toFixed(2)}:1 (${text} on ${ground})`)
  }
})

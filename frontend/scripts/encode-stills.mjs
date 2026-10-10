// Encodes the stills rendered by /dev/stills (landings spec, decision 26):
// public/landing/<name>.png → <name>.avif and <name>.webp, the AVIF within the
// speed budget (decision 30: 90 KB desktop, 50 KB phone). Exits 1 if one
// cannot fit. Run from frontend/: node scripts/encode-stills.mjs
import { readdirSync, statSync } from "node:fs"
import { fileURLToPath } from "node:url"
import sharp from "sharp"

const dir = fileURLToPath(new URL("../public/landing/", import.meta.url))
const BUDGET = { desktop: 90 * 1024, phone: 50 * 1024 }
let failed = false

for (const file of readdirSync(dir).filter((name) => name.endsWith(".png"))) {
  const base = file.slice(0, -4)
  const budget = base.endsWith("-desktop") ? BUDGET.desktop : BUDGET.phone
  let quality = 55
  let size = Infinity
  while (quality >= 25) {
    await sharp(`${dir}${file}`).avif({ quality, effort: 6 }).toFile(`${dir}${base}.avif`)
    size = statSync(`${dir}${base}.avif`).size
    if (size <= budget) break
    quality -= 10
  }
  await sharp(`${dir}${file}`).webp({ quality: 82, alphaQuality: 90, effort: 6 }).toFile(`${dir}${base}.webp`)
  const webp = statSync(`${dir}${base}.webp`).size
  const ok = size <= budget
  if (!ok) failed = true
  console.log(`${base}: avif ${(size / 1024).toFixed(1)} KB (q${quality}) ${ok ? "ok" : "OVER BUDGET"} · webp ${(webp / 1024).toFixed(1)} KB`)
}
if (failed) process.exit(1)

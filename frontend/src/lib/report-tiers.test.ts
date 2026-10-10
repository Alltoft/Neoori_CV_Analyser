import { test } from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { REPORT_TIERS } from "./report-tiers.ts"

// backend/app/services/section_registry.py, parcours 1:  _s("key", "Title"[, tiers=…])
const registry = readFileSync(new URL("../../../backend/app/services/section_registry.py", import.meta.url), "utf8")
const start = registry.indexOf("_P1 = [")
const p1 = registry.slice(start, registry.indexOf("\n]", start))
const backend = new Map(
  [...p1.matchAll(/_s\("(\w+)", "([^"]+)"(?:, tiers=(\w+|\(FREE,\)))?/g)].map((m) => [
    m[1],
    { title: m[2].replace(/'/g, "’"), tiers: m[3] ?? "ALL_TIERS" },
  ]),
)

test("the landing lists the report's real sections, in the backend's tiers (landings spec, decision 16)", () => {
  const allowed: Record<string, string[]> = { free: ["ALL_TIERS", "(FREE,)"], complet: ["PAID_UP"], premium: ["PREMIUM_ONLY"] }
  const seen = new Set<string>()
  for (const tier of REPORT_TIERS) {
    for (const row of tier.rows) {
      const entry = backend.get(row.key)
      assert.ok(entry, `§${row.key} is not in section_registry.py`)
      assert.equal(row.title, entry.title)
      assert.ok(allowed[tier.id].includes(entry.tiers), `§${row.key}: ${entry.tiers} in the backend, ${tier.id} on the landing`)
      seen.add(row.key)
    }
  }
  assert.deepEqual([...backend.keys()].filter((key) => !seen.has(key)), [])
})

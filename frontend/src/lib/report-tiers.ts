import { SECTION_TITLES } from "../types/index.ts"

/** The report's sections by tier, for the cv. landing (landings spec,
 *  decision 16). Titles are the report's own (SECTION_TITLES), with
 *  typographic apostrophes; report-tiers.test.ts checks them, and their tiers,
 *  against the backend's section_registry.py. */
export type TierId = "free" | "complet" | "premium"

export interface TierRow {
  key: string
  mark: string
  title: string
}

export interface Tier {
  id: TierId
  rows: TierRow[]
}

const rows = (keys: string[]): TierRow[] =>
  keys.map((key) => ({ key, mark: `§${key}`, title: SECTION_TITLES[key].replace(/'/g, "’") }))

export const REPORT_TIERS: Tier[] = [
  { id: "free", rows: [...rows(["1", "2", "3"]), { key: "verdict", mark: "✓", title: "Verdict" }] },
  { id: "complet", rows: rows(["4", "5", "6", "7", "8", "9"]) },
  { id: "premium", rows: rows(["10", "11"]) },
]

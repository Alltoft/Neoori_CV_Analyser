import { test } from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import {
  LOGO_LETTERS, LOGO_NAVY, LOGO_OO, LOGO_VIEWBOX, MARK_PATH, MARK_VIEWBOX,
} from "../components/brand/logo-paths.ts"

const svg = (name: string) => readFileSync(new URL(`../../public/brand/${name}`, import.meta.url), "utf8")

test("the logo paths are the vector files' own (run `npm run gen:logo` after changing them)", () => {
  const logo = svg("neoori-logo.svg")
  for (const d of Object.values(LOGO_LETTERS)) assert.ok(logo.includes(`d="${d}"`), d.slice(0, 20))
  assert.ok(logo.includes(`d="${LOGO_OO}"`))
  assert.ok(logo.includes(`fill="${LOGO_NAVY}"`))
  assert.deepEqual(LOGO_VIEWBOX, { w: 627, h: 175 })
  assert.ok(svg("neoori-mark.svg").includes(`d="${MARK_PATH}"`))
  assert.deepEqual(MARK_VIEWBOX, { w: 225, h: 131 })
})

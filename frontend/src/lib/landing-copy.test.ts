import { test } from "node:test"
import assert from "node:assert/strict"
import { cvCopy } from "../components/landing/copy/cv.ts"
import { voyageCopy } from "../components/landing/copy/voyage.ts"
import { footerCopy } from "../components/landing/copy/shared.ts"

function strings(value: unknown, out: string[] = []): string[] {
  if (typeof value === "string") out.push(value)
  else if (Array.isArray(value)) value.forEach((item) => strings(item, out))
  else if (value !== null && typeof value === "object") Object.values(value).forEach((item) => strings(item, out))
  return out
}

// Visible text only: hrefs start with "/" or "#".
const TEXT = [...strings(cvCopy), ...strings(voyageCopy), ...strings(footerCopy)]
  .filter((s) => !s.startsWith("/") && !s.startsWith("#"))

// CLAUDE.md, « UI copy rules ».
const BANNED = [
  "boussole", "copilote", "miroir", "révélation", "épanouissement",
  "alignement", "excellence", "talent unique", "vous vous démarquez",
]

test("no word from CLAUDE.md's banned list", () => {
  for (const s of TEXT) for (const word of BANNED) assert.ok(!s.toLowerCase().includes(word), `« ${word} » in « ${s} »`)
})

test("the cible is never only a job (landings spec, ruling 4)", () => {
  for (const s of TEXT) assert.doesNotMatch(s, /poste que vous visez|vous visez un poste|offre d['’]emploi/i, s)
})

test("French typography: typographic apostrophes and no-break spaces (decision 31)", () => {
  for (const s of TEXT) {
    assert.ok(!s.includes("'"), `straight apostrophe in « ${s} »`)
    assert.doesNotMatch(s, / [:;!?»]/, `plain space before punctuation in « ${s} »`)
    assert.doesNotMatch(s, /« /, `plain space after « in « ${s} »`)
  }
})

test("no score is promised and nothing claims where data is processed (decision 32)", () => {
  for (const s of TEXT) {
    if (/\bscore\b/i.test(s)) assert.match(s, /(ni|pas de) score/i, s)
    assert.doesNotMatch(s, /union européenne|\bUE\b|hébergée?s? en france/i, s)
  }
})

test("prices stay hidden until the PM agrees (decision 16)", () => {
  assert.equal(cvCopy.showPrices, false)
  assert.ok(cvCopy.nav.links.some((link) => link.pricesOnly))
})

test("the two doors and the advisors anchor line up (ruling 5)", () => {
  for (const copy of [cvCopy, voyageCopy]) {
    assert.equal(copy.hero.secondary.label, "Je suis conseiller")
    assert.equal(copy.hero.secondary.href, "#conseillers")
    assert.ok(copy.nav.links.some((link) => link.href === "/#conseillers"))
  }
  assert.equal(cvCopy.hero.primary.href, "/analyse/nouveau")
  assert.equal(voyageCopy.hero.primary.href, "/voyage")
})

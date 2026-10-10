import { test } from "node:test"
import assert from "node:assert/strict"
import { fr, typeset } from "./typeset.ts"

test("fr() sets the French no-break spaces (landings spec, decision 31)", () => {
  assert.equal(fr("Pour toute cible : un métier"), "Pour toute cible : un métier")
  assert.equal(fr("Une offre en main ? Collez-la ; merci !"), "Une offre en main ? Collez-la ; merci !")
  assert.equal(fr("oui, non ou « – »"), "oui, non ou « – »")
  assert.equal(fr("Complet · 9 € et 10 Mo"), "Complet · 9 € et 10 Mo")
  assert.equal(fr("/analyse/nouveau"), "/analyse/nouveau")
})

test("typeset() keeps the shape and leaves anything but strings alone", () => {
  assert.deepEqual(
    typeset({ a: "x : y", b: ["Et ? ", { c: false, d: 3 }] }),
    { a: "x : y", b: ["Et ? ", { c: false, d: 3 }] },
  )
})

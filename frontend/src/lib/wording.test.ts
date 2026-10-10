import { test } from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"

const read = (path: string) => readFileSync(new URL(`../${path}`, import.meta.url), "utf8")

// Landings spec, ruling 4: the cible is a métier, a formation, a poste or a
// projet. These phrases said it was only a job.
const PHRASES = [
  "poste que vous visez",
  "Vous visez un poste",
  "Le poste ou le secteur",
  "texte de l’offre d’emploi",
  "du point de vue des recruteurs",
  // Review finding: the root's own list of the report's sections.
  "pour ce poste précis",
  "Ce que le recruteur retient",
]

test("no page says the cible is only a job", () => {
  for (const file of ["app/layout.tsx", "app/page.tsx", "app/analyse/nouveau/page.tsx"]) {
    const source = read(file)
    for (const phrase of PHRASES) assert.ok(!source.includes(phrase), `${file} still says « ${phrase} »`)
  }
})

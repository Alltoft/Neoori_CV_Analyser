import { test } from "node:test"
import assert from "node:assert/strict"
import { homeFor } from "./home.ts"

test("a candidate's home is the espace on cv and the hub on voyage", () => {
  assert.equal(homeFor("candidate", "cv"), "/espace")
  assert.equal(homeFor("candidate", "voyage"), "/voyage")
  assert.equal(homeFor(undefined, "voyage"), "/voyage")
  assert.equal(homeFor("candidate", "root"), "/espace")
})

test("a counselor's and an admin's home are the same on every host", () => {
  for (const app of ["root", "cv", "voyage"] as const) {
    assert.equal(homeFor("counselor", app), "/conseiller")
    assert.equal(homeFor("admin", app), "/admin")
  }
})

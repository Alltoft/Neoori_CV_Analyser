import { test } from "node:test"
import assert from "node:assert/strict"
import { accountLink, visibleLinks } from "./landing-nav.ts"

test("« Mon espace » leads each role to its own home on this host (Review Focus 4)", () => {
  assert.deepEqual(accountLink(null, "cv"), { href: "/connexion", kind: "signin" })
  assert.deepEqual(accountLink("candidate", "cv"), { href: "/espace", kind: "home" })
  assert.deepEqual(accountLink("candidate", "voyage"), { href: "/voyage", kind: "home" })
  assert.deepEqual(accountLink("counselor", "voyage"), { href: "/conseiller", kind: "home" })
  assert.deepEqual(accountLink("admin", "cv"), { href: "/admin", kind: "home" })
})

test("« Tarifs » leaves the menu while prices are hidden (decision 16)", () => {
  const links = [{ href: "/#a", label: "A" }, { href: "/#tarifs", label: "Tarifs", pricesOnly: true }]
  assert.deepEqual(visibleLinks(links, false).map((l) => l.label), ["A"])
  assert.deepEqual(visibleLinks(links, true).map((l) => l.label), ["A", "Tarifs"])
})

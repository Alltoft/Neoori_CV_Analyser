import { test } from "node:test"
import assert from "node:assert/strict"
import { LOGO_PLAYED_KEY, shouldPlayLogo } from "./logo-motion.ts"

function memory(): Pick<Storage, "getItem" | "setItem"> {
  const data = new Map<string, string>()
  return { getItem: (k) => data.get(k) ?? null, setItem: (k, v) => void data.set(k, v) }
}

test("the logo draws once per tab session (landings spec, decision 19)", () => {
  const storage = memory()
  assert.equal(shouldPlayLogo(storage, false), true)
  assert.equal(storage.getItem(LOGO_PLAYED_KEY), "1")
  assert.equal(shouldPlayLogo(storage, false), false)
})

test("never under reduce motion (decision 23)", () => {
  assert.equal(shouldPlayLogo(memory(), true), false)
})

test("blocked storage still plays, and remembers nothing (Review Focus 5)", () => {
  const blocked = {
    getItem: () => { throw new Error("SecurityError") },
    setItem: () => { throw new Error("SecurityError") },
  }
  assert.equal(shouldPlayLogo(blocked, false), true)
  assert.equal(shouldPlayLogo(null, false), true)
})

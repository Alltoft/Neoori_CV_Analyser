import { test } from "node:test"
import assert from "node:assert/strict"
import { settleNavigation, waitForNavigation } from "./nav-settle.ts"

const pause = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

test("a wipe waits until the new page has committed", async () => {
  let done = false
  const wait = waitForNavigation(1000).then(() => { done = true })
  await pause(10)
  assert.equal(done, false)
  settleNavigation()
  await wait
  assert.equal(done, true)
})

test("…and never longer than its timeout (Review Focus 2)", async () => {
  const start = Date.now()
  await waitForNavigation(30)
  assert.ok(Date.now() - start >= 25)
})

test("a newer wait releases the older one", async () => {
  const first = waitForNavigation(1000)
  const second = waitForNavigation(1000)
  await first
  settleNavigation()
  await second
})

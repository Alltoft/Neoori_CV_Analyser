import { test } from "node:test"
import assert from "node:assert/strict"
import { RING_STROKE, ringSnapshot, wipeRadius } from "./wipe.ts"

test("the circle reaches the farthest corner, with a margin (landings spec, decision 22)", () => {
  assert.equal(wipeRadius(0, 0, 300, 400), 500 + 12)
  assert.equal(wipeRadius(150, 200, 300, 400), 250 + 12)
})

test("the ring's snapshot is at most 1200 px and keeps a 5 px stroke once scaled", () => {
  assert.deepEqual(ringSnapshot(400), { size: 800, stroke: RING_STROKE, scale: 1 })
  const big = ringSnapshot(1700)
  assert.equal(big.size, 1200)
  assert.ok(Math.abs(big.stroke * big.scale - RING_STROKE) < 1e-9)
})

import { test } from "node:test"
import assert from "node:assert/strict"
import { canRunLive3D, type DeviceInfo } from "./live-3d.ts"

const CAPABLE: DeviceInfo = { width: 1440, reducedMotion: false, webgl2: true }

test("a capable desktop gets the live 3D (landings spec, decision 24)", () => {
  assert.equal(canRunLive3D(CAPABLE), true)
  assert.equal(canRunLive3D({ ...CAPABLE, saveData: false, effectiveType: "4g", deviceMemory: 8, cores: 8 }), true)
})

test("anything else keeps the still image (Review Focus 5)", () => {
  const changes: Partial<DeviceInfo>[] = [
    { width: 900 }, { reducedMotion: true }, { webgl2: false }, { saveData: true },
    { effectiveType: "3g" }, { effectiveType: "slow-2g" }, { deviceMemory: 2 }, { cores: 2 },
  ]
  for (const change of changes) assert.equal(canRunLive3D({ ...CAPABLE, ...change }), false, JSON.stringify(change))
})

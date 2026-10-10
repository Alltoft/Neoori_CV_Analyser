import { test } from "node:test"
import assert from "node:assert/strict"

// A fake browser for the live 3D's render loop (landings spec, decision 24):
// animation-frame callbacks queue up and run on a rendering opportunity, and a
// hidden tab gets none, as in a real browser.
const listeners: Record<string, (() => void)[]> = {}
let hidden = false
let queue = new Map<number, () => void>()
let nextId = 1
let onIntersect: ((entries: { isIntersecting: boolean }[]) => void) | null = null
Object.assign(globalThis, {
  document: {
    get hidden() {
      return hidden
    },
    addEventListener: (type: string, listener: () => void) => {
      ;(listeners[type] ??= []).push(listener)
    },
    removeEventListener: (type: string, listener: () => void) => {
      listeners[type] = (listeners[type] ?? []).filter((other) => other !== listener)
    },
  },
  requestAnimationFrame: (callback: () => void) => {
    const id = nextId++
    queue.set(id, callback)
    return id
  },
  cancelAnimationFrame: (id: number) => {
    queue.delete(id)
  },
  IntersectionObserver: class {
    constructor(callback: (entries: { isIntersecting: boolean }[]) => void) {
      onIntersect = callback
    }
    observe() {}
    disconnect() {}
  },
})

const { runLoop } = await import("../components/landing/scenes/core.ts")

function frame() {
  if (hidden) return
  const due = [...queue.values()]
  queue = new Map()
  for (const callback of due) callback()
}

function setHidden(value: boolean) {
  hidden = value
  for (const listener of listeners.visibilitychange ?? []) listener()
}

test("the live 3D draws once per frame, however often the tab is switched (review finding)", () => {
  let renders = 0
  const pointerArea = {
    addEventListener() {},
    removeEventListener() {},
    getBoundingClientRect: () => ({ left: 0, top: 0, width: 1, height: 1 }),
  }
  const loop = runLoop(
    { render: () => void renders++ } as never,
    {} as HTMLElement,
    () => {},
    pointerArea as unknown as HTMLElement,
  )
  onIntersect?.([{ isIntersecting: true }])
  frame()
  for (let switches = 1; switches <= 5; switches++) {
    setHidden(true)
    setHidden(false)
    frame()
    const before = renders
    frame()
    assert.equal(renders - before, 1, `after ${switches} tab switch(es)`)
  }
  loop.stop()
  const before = renders
  frame()
  assert.equal(renders, before, "nothing is drawn once the loop has stopped")
})

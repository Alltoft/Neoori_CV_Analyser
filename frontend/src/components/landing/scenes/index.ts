import { createStage, runLoop, type Layout, type Stage, type Update } from "./core"
import { buildMark } from "./mark"
import { buildSheet } from "./sheet"

export type SceneKind = "sheet" | "mark"

export interface SceneController {
  dispose(): void
}

const SPECS: Record<SceneKind, {
  alpha: boolean
  background: string | null
  z: number
  maxPixelRatio: number
  build: (stage: Stage, layout: Layout) => Update
}> = {
  sheet: { alpha: true, background: null, z: 9.4, maxPixelRatio: 2, build: buildSheet },
  // Glass is the costly material: cap its pixel ratio at 1.5.
  mark: { alpha: false, background: "#1c3561", z: 9, maxPixelRatio: 1.5, build: buildMark },
}

/** The live scene, inside `host` (landings spec, decision 24). The caller
 *  decides whether it may run (lib/live-3d.ts). */
export function mountScene(
  kind: SceneKind,
  host: HTMLElement,
  opts: { layout: Layout; pointerArea: HTMLElement | null },
): SceneController {
  const spec = SPECS[kind]
  const stage = createStage(host, {
    alpha: spec.alpha,
    background: spec.background,
    z: spec.z,
    pixelRatio: Math.min(window.devicePixelRatio || 1, spec.maxPixelRatio),
    attach: true,
  })
  const update = spec.build(stage, opts.layout)
  const fit = () => stage.resize(host.clientWidth, host.clientHeight)
  const observer = new ResizeObserver(fit)
  observer.observe(host)
  fit()
  update(0, { x: 0, y: 0 })
  stage.render()
  const loop = runLoop(stage, host, update, opts.pointerArea ?? host)
  return {
    dispose() {
      loop.stop()
      observer.disconnect()
      stage.dispose()
    },
  }
}

/** One frame at t = 0, for the still images (decision 26). */
export function renderStill(
  kind: SceneKind,
  layout: Layout,
  width: number,
  height: number,
  pixelRatio: number,
): { canvas: HTMLCanvasElement; dispose(): void } {
  const spec = SPECS[kind]
  const stage = createStage(document.body, {
    alpha: spec.alpha,
    background: spec.background,
    z: spec.z,
    pixelRatio,
    attach: false,
    preserveDrawingBuffer: true,
  })
  const update = spec.build(stage, layout)
  stage.resize(width, height)
  update(0, { x: 0, y: 0 })
  stage.render()
  return { canvas: stage.renderer.domElement, dispose: () => stage.dispose() }
}

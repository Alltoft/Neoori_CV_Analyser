import * as THREE from "three"
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js"

/** Shared parts of the two landing scenes (landings spec, Appendix B). Only
 *  scenes/index.ts is imported from outside, and only through a dynamic
 *  import, so three.js never reaches the first-visit bundle. */

export type Layout = "desktop" | "phone"
export type Pointer = { x: number; y: number }
export type Update = (t: number, pointer: Pointer) => void
export type View = { w: number; h: number }

export interface Stage {
  renderer: THREE.WebGLRenderer
  scene: THREE.Scene
  camera: THREE.PerspectiveCamera
  /** Called with the visible size of the plane z = 0 whenever the canvas resizes. */
  onLayout: ((view: View) => void) | null
  view(): View
  resize(width: number, height: number): void
  render(): void
  dispose(): void
}

export const OO_COLORS = ["#ec6932", "#f49b68", "#f6b385"] as const

export function createStage(
  host: HTMLElement,
  o: { alpha: boolean; background: string | null; z: number; pixelRatio: number; attach: boolean; preserveDrawingBuffer?: boolean },
): Stage {
  const renderer = new THREE.WebGLRenderer({
    antialias: true,
    alpha: o.alpha,
    powerPreference: "high-performance",
    preserveDrawingBuffer: o.preserveDrawingBuffer ?? false,
  })
  renderer.setPixelRatio(o.pixelRatio)
  renderer.toneMapping = THREE.NeutralToneMapping
  renderer.outputColorSpace = THREE.SRGBColorSpace
  if (o.alpha) renderer.setClearColor(0x000000, 0)
  if (o.attach) host.appendChild(renderer.domElement)

  const scene = new THREE.Scene()
  if (o.background) scene.background = new THREE.Color(o.background)
  const room = new RoomEnvironment()
  const pmrem = new THREE.PMREMGenerator(renderer)
  const environment = pmrem.fromScene(room, 0.04)
  scene.environment = environment.texture
  pmrem.dispose()
  ;(room as unknown as { dispose?: () => void }).dispose?.()

  const camera = new THREE.PerspectiveCamera(28, 1, 0.1, 100)
  camera.position.set(0, 0, o.z)

  const stage: Stage = {
    renderer,
    scene,
    camera,
    onLayout: null,
    view() {
      const h = 2 * camera.position.z * Math.tan((camera.fov * Math.PI) / 360)
      return { w: h * camera.aspect, h }
    },
    resize(width, height) {
      if (!width || !height) return
      renderer.setSize(width, height, false)
      camera.aspect = width / height
      camera.updateProjectionMatrix()
      stage.onLayout?.(stage.view())
    },
    render() {
      renderer.render(scene, camera)
    },
    dispose() {
      scene.traverse((object) => {
        const mesh = object as THREE.Mesh
        mesh.geometry?.dispose()
        const materials = Array.isArray(mesh.material) ? mesh.material : mesh.material ? [mesh.material] : []
        for (const material of materials) {
          ;(material as THREE.MeshBasicMaterial).map?.dispose()
          material.dispose()
        }
      })
      environment.dispose()
      renderer.dispose()
      renderer.domElement.remove()
    },
  }
  return stage
}

/** Vertex colours along x: the oo's orange-to-peach gradient. */
export function paintGradient(geometry: THREE.BufferGeometry, colors: readonly string[] = OO_COLORS): THREE.BufferGeometry {
  const stops = colors.map((c) => new THREE.Color(c))
  geometry.computeBoundingBox()
  const box = geometry.boundingBox as THREE.Box3
  const position = geometry.getAttribute("position")
  const out = new Float32Array(position.count * 3)
  const color = new THREE.Color()
  const span = box.max.x - box.min.x || 1
  for (let i = 0; i < position.count; i++) {
    const t = (position.getX(i) - box.min.x) / span
    if (t < 0.5) color.copy(stops[0]).lerp(stops[1], t * 2)
    else color.copy(stops[1]).lerp(stops[2], (t - 0.5) * 2)
    out[i * 3] = color.r
    out[i * 3 + 1] = color.g
    out[i * 3 + 2] = color.b
  }
  geometry.setAttribute("color", new THREE.BufferAttribute(out, 3))
  return geometry
}

/** A radial gradient on a canvas texture, for glows and soft shadows. */
export function radialTexture(stops: ReadonlyArray<readonly [number, string]>, size = 512): THREE.CanvasTexture {
  const canvas = document.createElement("canvas")
  canvas.width = canvas.height = size
  const g = canvas.getContext("2d")
  if (!g) throw new Error("2d context unavailable")
  const gradient = g.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2)
  for (const [offset, color] of stops) gradient.addColorStop(offset, color)
  g.fillStyle = gradient
  g.fillRect(0, 0, size, size)
  const texture = new THREE.CanvasTexture(canvas)
  texture.colorSpace = THREE.SRGBColorSpace
  return texture
}

/** Runs `update` every frame while `host` is on screen and the tab visible;
 *  the pointer over `pointerArea` tilts the object a little. */
export function runLoop(stage: Stage, host: HTMLElement, update: Update, pointerArea: HTMLElement): { stop(): void } {
  const target = { x: 0, y: 0 }
  const current = { x: 0, y: 0 }
  let running = false
  let visible = false
  let stopped = false
  const t0 = performance.now()

  const frame = () => {
    if (!running || stopped) return
    current.x += (target.x - current.x) * 0.05
    current.y += (target.y - current.y) * 0.05
    update((performance.now() - t0) / 1000, current)
    stage.render()
    requestAnimationFrame(frame)
  }
  const sync = () => {
    const go = visible && !document.hidden && !stopped
    if (go && !running) {
      running = true
      requestAnimationFrame(frame)
    }
    if (!go) running = false
  }
  const move = (event: PointerEvent) => {
    const r = pointerArea.getBoundingClientRect()
    target.x = ((event.clientX - r.left) / r.width - 0.5) * 2
    target.y = ((event.clientY - r.top) / r.height - 0.5) * 2
  }
  const leave = () => {
    target.x = 0
    target.y = 0
  }
  pointerArea.addEventListener("pointermove", move, { passive: true })
  pointerArea.addEventListener("pointerleave", leave, { passive: true })
  const observer = new IntersectionObserver((entries) => {
    visible = entries.some((entry) => entry.isIntersecting)
    sync()
  }, { threshold: 0.02 })
  observer.observe(host)
  document.addEventListener("visibilitychange", sync)

  return {
    stop() {
      stopped = true
      running = false
      observer.disconnect()
      document.removeEventListener("visibilitychange", sync)
      pointerArea.removeEventListener("pointermove", move)
      pointerArea.removeEventListener("pointerleave", leave)
    },
  }
}

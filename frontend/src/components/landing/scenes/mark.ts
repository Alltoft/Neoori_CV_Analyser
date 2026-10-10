import * as THREE from "three"
import { SVGLoader } from "three/addons/loaders/SVGLoader.js"
import { MARK_PATH, MARK_VIEWBOX } from "@/components/brand/logo-paths"
import { radialTexture, type Layout, type Stage, type Update } from "./core"

const NAVY = "#1c3561"
const MARK_WIDTH = 225 * 0.0175 // the mark's width in world units at scale 1

/** voyage.: the oo mark extruded from the logo, in frosted glass, lit from
 *  below like dawn (landings spec, Appendix B). On desktop it is drawn in a
 *  square box, so the still and the live scene share one framing at every
 *  screen width (decision 26). */
export function buildMark(stage: Stage, layout: Layout): Update {
  const key = new THREE.DirectionalLight("#fff1e6", 1.4)
  key.position.set(3, 4, 5)
  stage.scene.add(key)
  const rim = new THREE.DirectionalLight("#f7b394", 2.2)
  rim.position.set(-4, -1, -3)
  stage.scene.add(rim)
  // The room's brightest panel sits behind the camera: facing it square on, as
  // at t = 0 (the still), the glass mirrors it and turns milky white. Turned
  // half round, the room lights the mark from behind, and it reads as glass
  // across the whole swing.
  stage.scene.environmentRotation.y = Math.PI

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${MARK_VIEWBOX.w} ${MARK_VIEWBOX.h}"><path d="${MARK_PATH}"/></svg>`
  const shapes = new SVGLoader().parse(svg).paths.flatMap((path) => SVGLoader.createShapes(path))
  const geometry = new THREE.ExtrudeGeometry(shapes, {
    depth: 22, curveSegments: 72, bevelEnabled: true, bevelThickness: 7, bevelSize: 3, bevelOffset: -3, bevelSegments: 8,
  })
  geometry.scale(1, -1, -1)
  geometry.center()
  // attenuationDistance is in world units: the mark is about 0.4 thick, so
  // 1.6 gives a light dawn tint (70–80 in round 1 gave no tint at all).
  const glass = new THREE.MeshPhysicalMaterial({
    color: "#ffeee4", roughness: 0.28, transmission: 1, thickness: 26, ior: 1.45,
    attenuationColor: new THREE.Color("#f2a27a"), attenuationDistance: 1.6, clearcoat: 1, clearcoatRoughness: 0.12,
  })
  const spin = new THREE.Group()
  spin.add(new THREE.Mesh(geometry, glass))
  spin.scale.setScalar(0.0175)
  const root = new THREE.Group()
  root.add(spin)
  stage.scene.add(root)

  // An opaque dawn glow behind the mark: the glass refracts it, and its edge
  // is exactly the page navy, so it melts into the background.
  const glow = new THREE.Mesh(
    new THREE.CircleGeometry(3.6, 96),
    new THREE.MeshBasicMaterial({ map: radialTexture([[0, "#8d6468"], [0.42, "#454468"], [1, NAVY]]), toneMapped: false }),
  )
  stage.scene.add(glow)

  stage.onLayout = (view) => {
    // Desktop: the mark fills 41.7 % of its square box and the glow about 92 %.
    // Phone: the round-2 prototype's framing.
    const scale = layout === "desktop" ? (0.417 * view.w) / MARK_WIDTH : Math.min(0.7, (0.62 * view.w) / MARK_WIDTH)
    const glowScale = layout === "desktop" ? 0.17 * view.w : Math.max(0.5, scale * 1.1)
    root.scale.setScalar(scale)
    glow.position.set(0, -0.45 * scale, -3)
    glow.scale.setScalar(glowScale)
  }

  return (t, pointer) => {
    spin.rotation.y = Math.sin(t * 0.45) * 0.32 + pointer.x * 0.35
    spin.rotation.x = -0.12 + Math.sin(t * 0.33) * 0.06 + pointer.y * 0.22
    spin.position.y = Math.sin(t * 0.8) * 0.06
  }
}

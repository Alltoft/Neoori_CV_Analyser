import * as THREE from "three"
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js"
import { paintGradient, radialTexture, type Layout, type Stage, type Update } from "./core"

/** cv.: an A4 sheet with the report's § marks, and the « cible » ring in
 *  matte ceramic (landings spec, Appendix B). At t = 0 it is exactly the
 *  still image. */
export function buildSheet(stage: Stage, layout: Layout): Update {
  const key = new THREE.DirectionalLight("#ffffff", 1.1)
  key.position.set(3, 5, 6)
  stage.scene.add(key)

  const root = new THREE.Group()
  const group = new THREE.Group()
  root.add(group)
  stage.scene.add(root)

  const paper = new THREE.MeshPhysicalMaterial({ color: "#ffffff", roughness: 0.62, clearcoat: 0.15, clearcoatRoughness: 0.6 })
  group.add(new THREE.Mesh(new RoundedBoxGeometry(2.1, 2.97, 0.06, 4, 0.05), paper))

  const bar = (w: number, h: number, x: number, y: number, color: string) => {
    const mesh = new THREE.Mesh(new RoundedBoxGeometry(w, h, 0.016, 2, 0.008), new THREE.MeshStandardMaterial({ color, roughness: 0.75 }))
    mesh.position.set(-0.85 + w / 2 + x, y, 0.036)
    group.add(mesh)
  }
  bar(0.38, 0.06, 0, 1.24, "#ea5624")
  bar(1.15, 0.11, 0, 1.06, "#1c3561")
  bar(0.8, 0.05, 0, 0.9, "#c7cfdc")
  for (const y of [0.62, -0.06, -0.74]) {
    bar(0.17, 0.1, 0, y, "#ea5624")
    bar(0.9, 0.08, 0.24, y, "#2b4677")
    ;[1.62, 1.5, 1.58, 1.2].forEach((w, i) => bar(w, 0.042, 0, y - 0.17 - i * 0.11, "#dfe5ee"))
  }

  const ceramic = new THREE.MeshPhysicalMaterial({ vertexColors: true, roughness: 0.44, metalness: 0, clearcoat: 0.5, clearcoatRoughness: 0.35 })
  const target = new THREE.Group()
  target.add(new THREE.Mesh(paintGradient(new THREE.TorusGeometry(0.52, 0.085, 48, 160)), ceramic))
  target.add(new THREE.Mesh(
    new THREE.SphereGeometry(0.07, 32, 32),
    new THREE.MeshPhysicalMaterial({ color: "#ea5624", roughness: 0.4, clearcoat: 0.6 }),
  ))
  target.position.set(0.5, 0.75, 0.75)
  target.rotation.set(0.25, -0.45, 0)
  group.add(target)

  const shadow = new THREE.Mesh(
    new THREE.PlaneGeometry(3.4, 4.2),
    new THREE.MeshBasicMaterial({
      map: radialTexture([[0, "rgba(28,53,97,0.28)"], [1, "rgba(28,53,97,0)"]]),
      transparent: true,
      depthWrite: false,
      toneMapped: false,
    }),
  )
  shadow.position.set(0.3, -0.35, -1.4)
  group.add(shadow)

  stage.onLayout = (view) => {
    if (layout === "desktop") {
      root.position.set(0.05, 0, 0)
      root.scale.setScalar(Math.min(1.12, view.w / 2.8))
    } else {
      root.position.set(0.05, -0.12, 0)
      root.scale.setScalar(Math.min(1.18, view.h / 3.9))
    }
  }

  return (t, pointer) => {
    group.position.y = Math.sin(t * 0.8) * 0.03
    group.rotation.set(
      -0.38 + Math.sin(t * 0.3) * 0.04 + pointer.y * 0.16,
      0.34 + Math.sin(t * 0.4) * 0.12 + pointer.x * 0.28,
      0.08,
    )
    target.position.y = 0.75 + Math.sin(t * 1.1) * 0.05
    target.rotation.z = Math.sin(t * 0.6) * 0.1
  }
}

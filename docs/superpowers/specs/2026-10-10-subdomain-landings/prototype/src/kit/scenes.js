// Round 2 — the two 3D objects picked in round 1, as reusable scenes.
// cv.:     an A4 sheet with the report's § marks, and the « cible » ring in matte ceramic.
// voyage.: the oo mark, extruded from the logo, in frosted glass, lit from below like dawn.
// Each scene pauses when off-screen or in a hidden tab, and stays still for reduce-motion.
import * as THREE from "three";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import { SVGLoader } from "three/addons/loaders/SVGLoader.js";

const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const OO = ["#ec6932", "#f49b68", "#f6b385"].map((c) => new THREE.Color(c));

function paintGradient(geo, stops = OO) {
  geo.computeBoundingBox();
  const { min, max } = geo.boundingBox, pos = geo.attributes.position;
  const out = new Float32Array(pos.count * 3), c = new THREE.Color();
  for (let i = 0; i < pos.count; i++) {
    const t = (pos.getX(i) - min.x) / (max.x - min.x || 1);
    if (t < 0.5) c.copy(stops[0]).lerp(stops[1], t * 2); else c.copy(stops[1]).lerp(stops[2], (t - 0.5) * 2);
    out[i * 3] = c.r; out[i * 3 + 1] = c.g; out[i * 3 + 2] = c.b;
  }
  geo.setAttribute("color", new THREE.BufferAttribute(out, 3));
  return geo;
}

function radialTexture(stops, size = 512) {
  const cv = document.createElement("canvas"); cv.width = cv.height = size;
  const g = cv.getContext("2d");
  const grd = g.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  stops.forEach(([o, c]) => grd.addColorStop(o, c));
  g.fillStyle = grd; g.fillRect(0, 0, size, size);
  const tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

function createStage(host, { alpha = false, background = null, fov = 28, z = 9 }) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha, powerPreference: "high-performance" });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.toneMapping = THREE.NeutralToneMapping;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  if (alpha) renderer.setClearColor(0x000000, 0);
  host.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  if (background) scene.background = new THREE.Color(background);
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  pmrem.dispose();
  const camera = new THREE.PerspectiveCamera(fov, 1, 0.1, 100);
  camera.position.set(0, 0, z);
  const st = {
    host, renderer, scene, camera, aspect: 1, onLayout: null,
    // Visible width and height of the plane z = 0, for placing objects by layout.
    view() { const h = 2 * camera.position.z * Math.tan((camera.fov * Math.PI) / 360); return { w: h * st.aspect, h }; },
    render() { renderer.render(scene, camera); },
  };
  st.fit = () => {
    const w = host.clientWidth, h = host.clientHeight; if (!w || !h) return;
    renderer.setSize(w, h, false);
    st.aspect = w / h; camera.aspect = st.aspect; camera.updateProjectionMatrix();
    if (st.onLayout) st.onLayout(st.aspect, st.view());
    st.render();
  };
  new ResizeObserver(st.fit).observe(host);
  return st;
}

function runLoop(st, update, pointerArea) {
  const target = { x: 0, y: 0 }, cur = { x: 0, y: 0 };
  let running = false, visible = false;
  const t0 = performance.now();
  const frame = () => {
    if (!running) return;
    cur.x += (target.x - cur.x) * 0.05; cur.y += (target.y - cur.y) * 0.05;
    update((performance.now() - t0) / 1000, cur); st.render();
    requestAnimationFrame(frame);
  };
  const sync = () => {
    const go = visible && !document.hidden && !reduce;
    if (go && !running) { running = true; requestAnimationFrame(frame); }
    if (!go) running = false;
  };
  if (!reduce) {
    const area = pointerArea || st.host;
    area.addEventListener("pointermove", (e) => {
      const r = area.getBoundingClientRect();
      target.x = ((e.clientX - r.left) / r.width - 0.5) * 2;
      target.y = ((e.clientY - r.top) / r.height - 0.5) * 2;
    });
    area.addEventListener("pointerleave", () => { target.x = 0; target.y = 0; });
  }
  new IntersectionObserver((es) => { visible = es.some((e) => e.isIntersecting); sync(); }, { threshold: 0.02 }).observe(st.host);
  document.addEventListener("visibilitychange", sync);
  update(0, cur); st.render();
}

function failSoft(host, err) {
  console.error(err);
  host.setAttribute("data-3d", "off");
}

export function mountSheet(host, { alpha = true, background = null, pointerArea = null, layout = null } = {}) {
  try {
    const st = createStage(host, { alpha, background, z: 9.4 });
    const key = new THREE.DirectionalLight("#ffffff", 1.1); key.position.set(3, 5, 6); st.scene.add(key);
    const root = new THREE.Group(); st.scene.add(root);
    const group = new THREE.Group(); root.add(group);

    const paper = new THREE.MeshPhysicalMaterial({ color: "#ffffff", roughness: 0.62, clearcoat: 0.15, clearcoatRoughness: 0.6 });
    group.add(new THREE.Mesh(new RoundedBoxGeometry(2.1, 2.97, 0.06, 4, 0.05), paper));
    const bar = (w, h, x, y, color) => {
      const m = new THREE.Mesh(new RoundedBoxGeometry(w, h, 0.016, 2, 0.008), new THREE.MeshStandardMaterial({ color, roughness: 0.75 }));
      m.position.set(-0.85 + w / 2 + x, y, 0.036); group.add(m);
    };
    bar(0.38, 0.06, 0, 1.24, "#ea5624");
    bar(1.15, 0.11, 0, 1.06, "#1c3561");
    bar(0.8, 0.05, 0, 0.9, "#c7cfdc");
    [0.62, -0.06, -0.74].forEach((y) => {
      bar(0.17, 0.1, 0, y, "#ea5624");
      bar(0.9, 0.08, 0.24, y, "#2b4677");
      [1.62, 1.5, 1.58, 1.2].forEach((w, i) => bar(w, 0.042, 0, y - 0.17 - i * 0.11, "#dfe5ee"));
    });

    const ceramic = new THREE.MeshPhysicalMaterial({ vertexColors: true, roughness: 0.44, metalness: 0, clearcoat: 0.5, clearcoatRoughness: 0.35 });
    const target = new THREE.Group();
    target.add(new THREE.Mesh(paintGradient(new THREE.TorusGeometry(0.52, 0.085, 48, 160)), ceramic));
    target.add(new THREE.Mesh(new THREE.SphereGeometry(0.07, 32, 32), new THREE.MeshPhysicalMaterial({ color: "#ea5624", roughness: 0.4, clearcoat: 0.6 })));
    target.position.set(0.5, 0.75, 0.75); target.rotation.set(0.25, -0.45, 0);
    group.add(target);

    const shadow = new THREE.Mesh(new THREE.PlaneGeometry(3.4, 4.2), new THREE.MeshBasicMaterial({
      map: radialTexture([[0, "rgba(28,53,97,0.28)"], [1, "rgba(28,53,97,0)"]]), transparent: true, depthWrite: false, toneMapped: false,
    }));
    shadow.position.set(0.3, -0.35, -1.4); group.add(shadow);

    st.onLayout = (aspect, view) => {
      const l = layout ? layout(aspect, view) : { x: 0, y: 0, s: 1 };
      root.position.set(l.x, l.y, 0); root.scale.setScalar(l.s);
    };
    st.fit();
    runLoop(st, (t, p) => {
      group.position.y = Math.sin(t * 0.8) * 0.03;
      group.rotation.set(-0.38 + Math.sin(t * 0.3) * 0.04 + p.y * 0.16, 0.34 + Math.sin(t * 0.4) * 0.12 + p.x * 0.28, 0.08);
      target.position.y = 0.75 + Math.sin(t * 1.1) * 0.05;
      target.rotation.z = Math.sin(t * 0.6) * 0.1;
    }, pointerArea);
    return st;
  } catch (err) { failSoft(host, err); return null; }
}

export function mountMark(host, { markPath, background = "#1c3561", pointerArea = null, layout = null } = {}) {
  try {
    const st = createStage(host, { background, z: 9 });
    const key = new THREE.DirectionalLight("#fff1e6", 1.4); key.position.set(3, 4, 5); st.scene.add(key);
    const rim = new THREE.DirectionalLight("#f7b394", 2.2); rim.position.set(-4, -1, -3); st.scene.add(rim);

    const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 225 131"><path d="${markPath}"/></svg>`;
    const shapes = new SVGLoader().parse(svg).paths.flatMap((p) => SVGLoader.createShapes(p));
    const geo = new THREE.ExtrudeGeometry(shapes, { depth: 22, curveSegments: 72, bevelEnabled: true, bevelThickness: 7, bevelSize: 3, bevelOffset: -3, bevelSegments: 8 });
    geo.scale(1, -1, -1); geo.center();
    const glass = new THREE.MeshPhysicalMaterial({
      // attenuationDistance is in world units (the mark is ~0.4 thick): 1.6 gives a light dawn tint.
      color: "#ffeee4", roughness: 0.28, transmission: 1, thickness: 26, ior: 1.45,
      attenuationColor: new THREE.Color("#f2a27a"), attenuationDistance: 1.6, clearcoat: 1, clearcoatRoughness: 0.12,
    });
    const mark = new THREE.Mesh(geo, glass);
    const spin = new THREE.Group(); spin.add(mark); spin.scale.setScalar(0.0175);
    const root = new THREE.Group(); root.add(spin); st.scene.add(root);

    // An opaque dawn glow behind the mark: the glass refracts it, and its edge
    // is exactly the page navy, so it melts into the background.
    const glow = new THREE.Mesh(new THREE.CircleGeometry(3.6, 96), new THREE.MeshBasicMaterial({
      map: radialTexture([[0, "#8d6468"], [0.42, "#454468"], [1, background]]), toneMapped: false,
    }));
    st.scene.add(glow);

    st.onLayout = (aspect, view) => {
      const l = layout ? layout(aspect, view) : { x: 0, y: 0, s: 1 };
      root.position.set(l.x, l.y, 0); root.scale.setScalar(l.s);
      glow.position.set(l.x, l.y - 0.45 * l.s, -3); glow.scale.setScalar(Math.max(0.5, l.s * 1.1));
    };
    st.fit();
    runLoop(st, (t, p) => {
      spin.rotation.y = Math.sin(t * 0.45) * 0.32 + p.x * 0.35;
      spin.rotation.x = -0.12 + Math.sin(t * 0.33) * 0.06 + p.y * 0.22;
      spin.position.y = Math.sin(t * 0.8) * 0.06;
    }, pointerArea);
    return st;
  } catch (err) { failSoft(host, err); return null; }
}

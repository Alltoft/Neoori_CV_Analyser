/** Whether the live 3D may replace the still image (landings spec, decision
 *  24). Unknown values (browsers that do not report them) do not block. */
export interface DeviceInfo {
  width: number
  reducedMotion: boolean
  saveData?: boolean
  effectiveType?: string
  deviceMemory?: number
  cores?: number
  webgl2: boolean
}

const SLOW = ["slow-2g", "2g", "3g"]

export function canRunLive3D(d: DeviceInfo): boolean {
  if (d.width <= 900 || d.reducedMotion || !d.webgl2) return false
  if (d.saveData === true) return false
  if (d.effectiveType !== undefined && SLOW.includes(d.effectiveType)) return false
  if (d.deviceMemory !== undefined && d.deviceMemory < 4) return false
  if (d.cores !== undefined && d.cores < 4) return false
  return true
}

type NetworkInformation = { saveData?: boolean; effectiveType?: string }

/** DeviceInfo from the browser. The WebGL 2 probe frees its context at once. */
export function readDevice(w: Window): DeviceInfo {
  const nav = w.navigator as Navigator & { connection?: NetworkInformation; deviceMemory?: number }
  let webgl2 = false
  try {
    const gl = w.document.createElement("canvas").getContext("webgl2")
    webgl2 = gl !== null
    gl?.getExtension("WEBGL_lose_context")?.loseContext()
  } catch {
    webgl2 = false
  }
  return {
    width: w.innerWidth,
    reducedMotion: w.matchMedia("(prefers-reduced-motion: reduce)").matches,
    saveData: nav.connection?.saveData,
    effectiveType: nav.connection?.effectiveType,
    deviceMemory: nav.deviceMemory,
    cores: nav.hardwareConcurrency,
    webgl2,
  }
}

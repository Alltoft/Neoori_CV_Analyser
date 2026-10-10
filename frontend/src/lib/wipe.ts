/** Geometry of the ∞ wipe (landings spec, decision 22). */

export const RING_STROKE = 5

/** The radius that covers the viewport from (x, y), with a small margin. */
export function wipeRadius(x: number, y: number, width: number, height: number): number {
  return Math.hypot(Math.max(x, width - x), Math.max(y, height - y)) + 12
}

/** The ring is captured once, at `size` px at most, and its transition layer
 *  is scaled up by `scale`; the stroke is drawn thinner by the same factor so
 *  that it ends at RING_STROKE px. */
export function ringSnapshot(radius: number, maxSize = 1200): { size: number; stroke: number; scale: number } {
  const diameter = 2 * radius
  const size = Math.min(diameter, maxSize)
  return { size, stroke: (RING_STROKE * size) / diameter, scale: diameter / size }
}

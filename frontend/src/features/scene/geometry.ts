export type Point3 = readonly [number, number, number]

export interface SurfacePoint {
  position: Point3
  scale: number
}

/** Small deterministic generator, so the bacterium looks identical on every load and in every test. */
export function seededRandom(seed: number): () => number {
  let state = seed >>> 0
  return () => {
    state = (state + 0x6d2b79f5) >>> 0
    let t = state
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

/**
 * Points on the surface of a capsule lying along the Y axis (a cylinder of length 2 * halfLength with hemispherical
 * caps), spread by area. They carry the surface bumps that give the E. coli its texture.
 */
export function capsuleSurfacePoints(count: number, radius: number, halfLength: number, seed: number): SurfacePoint[] {
  const random = seededRandom(seed)
  const cylinderArea = 2 * Math.PI * radius * 2 * halfLength
  const capsArea = 4 * Math.PI * radius * radius
  const cylinderShare = cylinderArea / (cylinderArea + capsArea)

  return Array.from({ length: count }, () => {
    const scale = 0.7 + random() * 0.6
    if (random() < cylinderShare) {
      const angle = random() * Math.PI * 2
      const y = (random() * 2 - 1) * halfLength
      return { position: [Math.cos(angle) * radius, y, Math.sin(angle) * radius] as const, scale }
    }
    // A uniform direction on the sphere, placed on whichever cap it points toward.
    const z = random() * 2 - 1
    const angle = random() * Math.PI * 2
    const ring = Math.sqrt(1 - z * z)
    const up = z >= 0 ? 1 : -1
    return {
      position: [Math.cos(angle) * ring * radius, up * halfLength + Math.abs(z) * up * radius, Math.sin(angle) * ring * radius] as const,
      scale,
    }
  })
}

/** Where marker `index` of `count` sits on a circle around the bacterium: the first at the top, then clockwise. */
export function markerPosition(index: number, count: number, radius: number): Point3 {
  const angle = -Math.PI / 2 + (index * Math.PI * 2) / count
  return [Math.cos(angle) * radius, -Math.sin(angle) * radius, 0]
}

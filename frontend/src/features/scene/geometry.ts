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

const length = (vector: Point3) => Math.hypot(vector[0], vector[1], vector[2])
const normalize = (vector: Point3): Point3 => {
  const size = length(vector) || 1
  return [vector[0] / size, vector[1] / size, vector[2] / size]
}
const cross = (a: Point3, b: Point3): Point3 => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]

/** The outward direction at a point on the capsule surface: radial on the cylinder, away from the cap's centre on the caps. */
export function surfaceNormal(position: Point3, halfLength: number): Point3 {
  const [x, y, z] = position
  if (Math.abs(y) <= halfLength) {
    return normalize([x, 0, z])
  }
  return normalize([x, y - Math.sign(y) * halfLength, z])
}

export interface FlagellumShape {
  length: number
  segments: number
  /** Radius of the corkscrew, reached gradually along the filament. */
  amplitude: number
  turns: number
  phase: number
  /** Direction (angle around the filament's axis) and strength (fraction of length) of the slow sideways drift. */
  bendAngle: number
  bend: number
}

/** A wavy filament leaving the surface at `origin` along `normal`: a corkscrew that starts on the body and drifts to one side. */
export function flagellumPath(origin: Point3, normal: Point3, shape: FlagellumShape): Point3[] {
  const axis = normalize(normal)
  const helper: Point3 = Math.abs(axis[0]) < 0.9 ? [1, 0, 0] : [0, 1, 0]
  const u = normalize(cross(axis, helper))
  const v = cross(axis, u)
  const drift: Point3 = [
    u[0] * Math.cos(shape.bendAngle) + v[0] * Math.sin(shape.bendAngle),
    u[1] * Math.cos(shape.bendAngle) + v[1] * Math.sin(shape.bendAngle),
    u[2] * Math.cos(shape.bendAngle) + v[2] * Math.sin(shape.bendAngle),
  ]

  return Array.from({ length: shape.segments + 1 }, (_, index) => {
    const t = index / shape.segments
    const angle = Math.PI * 2 * shape.turns * t + shape.phase
    const wave = shape.amplitude * Math.min(1, t * 4) * (0.5 + 0.5 * t)
    const along = shape.length * t
    const sideways = shape.bend * shape.length * t * t
    return [
      origin[0] + axis[0] * along + drift[0] * sideways + (u[0] * Math.cos(angle) + v[0] * Math.sin(angle)) * wave,
      origin[1] + axis[1] * along + drift[1] * sideways + (u[1] * Math.cos(angle) + v[1] * Math.sin(angle)) * wave,
      origin[2] + axis[2] * along + drift[2] * sideways + (u[2] * Math.cos(angle) + v[2] * Math.sin(angle)) * wave,
    ] as const
  })
}

/** Short straight hairs (fimbriae) standing on the surface: where each starts and which way it points. */
export function fimbriaPlacements(count: number, radius: number, halfLength: number, seed: number): { position: Point3; normal: Point3; scale: number }[] {
  return capsuleSurfacePoints(count, radius, halfLength, seed).map(({ position, scale }) => ({ position, normal: surfaceNormal(position, halfLength), scale }))
}

/** Where marker `index` of `count` sits on a circle around the bacterium: the first at the top, then clockwise. */
export function markerPosition(index: number, count: number, radius: number): Point3 {
  const angle = -Math.PI / 2 + (index * Math.PI * 2) / count
  return [Math.cos(angle) * radius, -Math.sin(angle) * radius, 0]
}

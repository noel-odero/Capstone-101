import { describe, expect, it } from 'vitest'
import { capsuleSurfacePoints, fimbriaPlacements, flagellumPath, surfaceNormal, type Point3 } from './geometry'

const distance = (a: Point3, b: Point3) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2])
const size = (v: Point3) => Math.hypot(v[0], v[1], v[2])
const RADIUS = 0.55
const HALF = 0.95

describe('E. coli geometry', () => {
  it('points the surface normal outward: radial on the side, away from the centre on the caps', () => {
    expect(surfaceNormal([RADIUS, 0.3, 0], HALF)).toEqual([1, 0, 0])
    const top = surfaceNormal([0, HALF + RADIUS, 0], HALF)
    expect(top[1]).toBeCloseTo(1)
    const slanted = surfaceNormal([RADIUS * 0.6, -(HALF + RADIUS * 0.8), 0], HALF)
    expect(slanted[1]).toBeLessThan(0)
    expect(slanted[0]).toBeGreaterThan(0)
    expect(size(slanted)).toBeCloseTo(1)
  })

  it('places every fimbria on the surface with a unit normal, identically on every call', () => {
    const first = fimbriaPlacements(60, RADIUS, HALF, 3)
    expect(fimbriaPlacements(60, RADIUS, HALF, 3)).toEqual(first)
    expect(first).toHaveLength(60)
    for (const { normal } of first) {
      expect(size(normal)).toBeCloseTo(1)
    }
  })

  it('draws a flagellum that starts on the body, reaches its length, and wiggles rather than running straight', () => {
    const origin: Point3 = [RADIUS, 0.2, 0]
    const path = flagellumPath(origin, [1, 0, 0], { length: 2, segments: 40, amplitude: 0.1, turns: 3, phase: 0, bendAngle: 1, bend: 0.2 })

    expect(path).toHaveLength(41)
    expect(distance(path[0] as Point3, origin)).toBeCloseTo(0, 6)
    expect(distance(path[40] as Point3, origin)).toBeGreaterThan(1.9)
    const straight = Math.hypot(...(path[40] as Point3).map((value, axis) => value - (origin[axis] ?? 0)))
    const travelled = path.slice(1).reduce((sum, point, index) => sum + distance(point, path[index] as Point3), 0)
    expect(travelled).toBeGreaterThan(straight * 1.05)
  })

  it('keeps the body points deterministic for a seed', () => {
    expect(capsuleSurfacePoints(20, RADIUS, HALF, 9)).toEqual(capsuleSurfacePoints(20, RADIUS, HALF, 9))
    expect(capsuleSurfacePoints(20, RADIUS, HALF, 9)).not.toEqual(capsuleSurfacePoints(20, RADIUS, HALF, 10))
  })
})

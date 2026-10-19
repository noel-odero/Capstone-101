import { describe, expect, it } from 'vitest'
import { Vector3 } from 'three'
import { MAX_DISTANCE, MIN_DISTANCE, orbitedPosition, zoomedPosition } from './sceneCamera'

describe('scene camera helpers', () => {
  const target = new Vector3(0, -0.45, 0)
  const start = new Vector3(0, -0.2, 9.8)

  it('moves toward the target when zooming in and away when zooming out', () => {
    const closer = zoomedPosition(start, target, 0.8)
    const farther = zoomedPosition(start, target, 1.2)
    expect(closer.distanceTo(target)).toBeLessThan(start.distanceTo(target))
    expect(farther.distanceTo(target)).toBeGreaterThan(start.distanceTo(target))
  })

  it('never zooms past the configured bounds', () => {
    expect(zoomedPosition(start, target, 0.0001).distanceTo(target)).toBeCloseTo(MIN_DISTANCE, 5)
    expect(zoomedPosition(start, target, 1000).distanceTo(target)).toBeCloseTo(MAX_DISTANCE, 5)
  })

  it('orbits around the vertical axis without changing distance or height', () => {
    const turned = orbitedPosition(start, target, Math.PI / 8)
    expect(turned.distanceTo(target)).toBeCloseTo(start.distanceTo(target), 5)
    expect(turned.y).toBeCloseTo(start.y, 5)
    expect(turned.x).not.toBeCloseTo(start.x, 3)
  })

  it('does not mutate its inputs', () => {
    const before = start.clone()
    zoomedPosition(start, target, 0.5)
    orbitedPosition(start, target, 1)
    expect(start.equals(before)).toBe(true)
  })
})

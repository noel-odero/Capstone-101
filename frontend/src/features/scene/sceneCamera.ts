import { Vector3 } from 'three'

export const MIN_DISTANCE = 4.5
export const MAX_DISTANCE = 14
const UP = new Vector3(0, 1, 0)

/** Camera position after moving toward (factor < 1) or away from (factor > 1) the target, kept within the zoom bounds. */
export function zoomedPosition(position: Vector3, target: Vector3, factor: number): Vector3 {
  const offset = position.clone().sub(target)
  const distance = Math.min(MAX_DISTANCE, Math.max(MIN_DISTANCE, offset.length() * factor))
  return target.clone().add(offset.setLength(distance))
}

/** Camera position after orbiting the target around the vertical axis by `radians`. */
export function orbitedPosition(position: Vector3, target: Vector3, radians: number): Vector3 {
  const offset = position.clone().sub(target).applyAxisAngle(UP, radians)
  return target.clone().add(offset)
}

import { useLayoutEffect, useMemo, useRef } from 'react'
import { Object3D, type InstancedMesh } from 'three'
import { capsuleSurfacePoints } from './geometry'
import { SCENE_COLORS } from './sceneColors'

interface EcoliBodyProps {
  radius?: number
  halfLength?: number
  color?: string
  bumpColor?: string
  bumpCount?: number
  seed?: number
}

/** A rod-shaped E. coli: a glossy capsule studded with small bumps. Stable shape, no animation of its own. */
export function EcoliBody({
  radius = 0.55,
  halfLength = 0.95,
  color = SCENE_COLORS.bacterium,
  bumpColor = SCENE_COLORS.bacteriumBump,
  bumpCount = 220,
  seed = 7,
}: EcoliBodyProps) {
  const points = useMemo(() => capsuleSurfacePoints(bumpCount, radius * 0.99, halfLength, seed), [bumpCount, radius, halfLength, seed])
  const bumps = useRef<InstancedMesh>(null)

  useLayoutEffect(() => {
    const mesh = bumps.current
    if (!mesh) {
      return
    }
    const helper = new Object3D()
    points.forEach((point, index) => {
      helper.position.set(point.position[0], point.position[1], point.position[2])
      helper.scale.setScalar(point.scale)
      helper.updateMatrix()
      mesh.setMatrixAt(index, helper.matrix)
    })
    mesh.instanceMatrix.needsUpdate = true
  }, [points])

  return (
    <group>
      <mesh>
        <capsuleGeometry args={[radius, halfLength * 2, 16, 40]} />
        <meshPhysicalMaterial color={color} roughness={0.35} metalness={0.05} clearcoat={0.6} clearcoatRoughness={0.3} emissive={SCENE_COLORS.bacteriumDeep} emissiveIntensity={0.35} />
      </mesh>
      <instancedMesh ref={bumps} args={[undefined, undefined, points.length]}>
        <sphereGeometry args={[radius * 0.1, 10, 8]} />
        <meshStandardMaterial color={bumpColor} roughness={0.45} />
      </instancedMesh>
    </group>
  )
}

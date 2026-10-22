import { useLayoutEffect, useMemo, useRef } from 'react'
import { CatmullRomCurve3, Object3D, Quaternion, Vector3, type InstancedMesh } from 'three'
import { capsuleSurfacePoints, fimbriaPlacements, flagellumPath, seededRandom, surfaceNormal } from './geometry'
import { SCENE_COLORS } from './sceneColors'

interface EcoliBodyProps {
  radius?: number
  halfLength?: number
  color?: string
  bumpColor?: string
  bumpCount?: number
  /** Long wavy filaments that leave the cell. */
  flagellaCount?: number
  /** Short straight hairs standing on the surface. */
  fimbriaCount?: number
  seed?: number
}

const UP = new Vector3(0, 1, 0)

/** A rod-shaped E. coli: a glossy capsule with surface bumps, short fimbriae and a few long wavy flagella. Stable shape, no animation of its own. */
export function EcoliBody({
  radius = 0.55,
  halfLength = 0.95,
  color = SCENE_COLORS.bacterium,
  bumpColor = SCENE_COLORS.bacteriumBump,
  bumpCount = 220,
  flagellaCount = 7,
  fimbriaCount = 170,
  seed = 7,
}: EcoliBodyProps) {
  const points = useMemo(() => capsuleSurfacePoints(bumpCount, radius * 0.99, halfLength, seed), [bumpCount, radius, halfLength, seed])
  const fimbriae = useMemo(() => fimbriaPlacements(fimbriaCount, radius, halfLength, seed + 11), [fimbriaCount, radius, halfLength, seed])
  const flagella = useMemo(() => {
    const random = seededRandom(seed + 29)
    return capsuleSurfacePoints(flagellaCount, radius, halfLength, seed + 5).map(({ position }) => {
      const path = flagellumPath(position, surfaceNormal(position, halfLength), {
        length: radius * (2.6 + random() * 1),
        segments: 40,
        amplitude: radius * (0.14 + random() * 0.08),
        turns: 2.6 + random() * 1.4,
        phase: random() * Math.PI * 2,
        bendAngle: random() * Math.PI * 2,
        bend: 0.18 + random() * 0.14,
      })
      return new CatmullRomCurve3(path.map(([x, y, z]) => new Vector3(x, y, z)))
    })
  }, [flagellaCount, radius, halfLength, seed])

  const bumps = useRef<InstancedMesh>(null)
  const hairs = useRef<InstancedMesh>(null)

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

  useLayoutEffect(() => {
    const mesh = hairs.current
    if (!mesh) {
      return
    }
    const helper = new Object3D()
    const direction = new Vector3()
    const hairLength = radius * 0.55
    fimbriae.forEach(({ position, normal, scale }, index) => {
      direction.set(normal[0], normal[1], normal[2])
      const size = hairLength * scale
      helper.position.set(position[0] + normal[0] * (size / 2), position[1] + normal[1] * (size / 2), position[2] + normal[2] * (size / 2))
      helper.quaternion.copy(new Quaternion().setFromUnitVectors(UP, direction))
      helper.scale.set(1, size, 1)
      helper.updateMatrix()
      mesh.setMatrixAt(index, helper.matrix)
    })
    mesh.instanceMatrix.needsUpdate = true
  }, [fimbriae, radius])

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
      <instancedMesh ref={hairs} args={[undefined, undefined, fimbriae.length]}>
        <cylinderGeometry args={[radius * 0.013, radius * 0.013, 1, 5]} />
        <meshStandardMaterial color={SCENE_COLORS.bacteriumRim} roughness={0.5} />
      </instancedMesh>
      {flagella.map((curve, index) => (
        <mesh key={index}>
          <tubeGeometry args={[curve, 64, radius * 0.045, 6, false]} />
          <meshStandardMaterial color={SCENE_COLORS.bacteriumRim} emissive={SCENE_COLORS.bacteriumBump} emissiveIntensity={0.25} roughness={0.5} />
        </mesh>
      ))}
    </group>
  )
}

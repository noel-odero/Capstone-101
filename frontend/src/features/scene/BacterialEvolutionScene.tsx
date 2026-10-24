import { useFrame, useThree } from '@react-three/fiber'
import { useEffect, useMemo, useRef } from 'react'
import {
  CapsuleGeometry,
  CatmullRomCurve3,
  Color,
  Float32BufferAttribute,
  Vector3,
  type Group,
} from 'three'
import type { ResistanceProfile } from '@/domain/types'
import { SceneFrame } from './SceneFrame'
import { prefersReducedMotion } from './sceneSupport'
import { UrinaryTractModel } from './UrinaryTractModel'
import styles from './evolution-scene.module.css'

const susceptible = new Color('#68e4bc')
const resistant = new Color('#fb7185')

// The seven membrane regions encode the stored binary phenotype, not physical resistance sites.
function membraneColors(geometry: CapsuleGeometry, profile: ResistanceProfile) {
  const positions = geometry.getAttribute('position')
  const colors = new Float32Array(positions.count * 3)
  for (let index = 0; index < positions.count; index++) {
    const y = positions.getY(index)
    const region = Math.max(0, Math.min(6, Math.floor(((y + 1.265) / 2.53) * 7)))
    const tint = profile[region] === 1 ? resistant : susceptible
    const texture = 0.84 + 0.16 * Math.sin(y * 43 + positions.getX(index) * 27) ** 2
    colors[index * 3] = tint.r * texture
    colors[index * 3 + 1] = tint.g * texture
    colors[index * 3 + 2] = tint.b * texture
  }
  return colors
}

function Bacterium({
  profile,
  before,
  animate,
  anatomy,
}: {
  profile: ResistanceProfile
  before: ResistanceProfile
  animate: boolean
  anatomy: boolean
}) {
  const group = useRef<Group>(null)
  const elapsed = useRef(0)
  const invalidate = useThree((state) => state.invalidate)
  const reduced = prefersReducedMotion()
  const geometry = useMemo(() => new CapsuleGeometry(0.44, 1.65, 16, 48, 56), [])
  const initialColors = useMemo(() => membraneColors(geometry, before), [geometry, before])
  const targetColors = useMemo(() => membraneColors(geometry, profile), [geometry, profile])
  const flagella = useMemo(
    () =>
      Array.from({ length: 7 }, (_, index) => {
        const angle = (index / 7) * Math.PI * 2
        return new CatmullRomCurve3(
          Array.from({ length: 26 }, (_, point) => {
            const t = point / 25
            return new Vector3(
              Math.cos(angle) * 0.22 + Math.sin(t * 8 + angle) * t * 0.22,
              -1.12 - t * (0.6 + (index % 3) * 0.13),
              Math.sin(angle) * 0.22 + Math.cos(t * 8 + angle) * t * 0.22,
            )
          }),
        )
      }),
    [],
  )
  useEffect(() => {
    geometry.setAttribute(
      'color',
      new Float32BufferAttribute(reduced ? targetColors : initialColors, 3),
    )
    invalidate()
  }, [geometry, initialColors, targetColors, reduced, invalidate])
  useEffect(() => () => geometry.dispose(), [geometry])
  useFrame((_, delta) => {
    const attribute = geometry.getAttribute('color')
    if (attribute) {
      let settling = false
      const amount = reduced ? 1 : 1 - Math.exp(-Math.min(delta, 0.05) * 7)
      for (let index = 0; index < targetColors.length; index++) {
        const current = attribute.array[index] ?? 0
        const target = targetColors[index] ?? 0
        const difference = target - current
        attribute.array[index] =
          Math.abs(difference) < 0.001 ? target : current + difference * amount
        settling ||= Math.abs(difference) >= 0.001
      }
      attribute.needsUpdate = true
      if (settling) invalidate()
    }
    if (animate && !reduced && group.current) {
      elapsed.current += Math.min(delta, 0.05)
      group.current.position.y = Math.sin(elapsed.current * 0.6) * 0.045
      group.current.rotation.y = 0.22 + Math.sin(elapsed.current * 0.4) * 0.12
    }
  })
  return (
    <group position={anatomy ? [1.55, 0.15, 0.4] : [0, 0.15, 0]} scale={anatomy ? 0.8 : 1}>
      <group ref={group} rotation={[0.12, 0.22, -0.75]}>
        <mesh geometry={geometry}>
          <meshPhysicalMaterial
            vertexColors
            roughness={0.36}
            metalness={0.1}
            clearcoat={0.9}
            clearcoatRoughness={0.35}
          />
        </mesh>
        {Array.from({ length: 44 }, (_, index) => {
          const angle = index * 2.39996
          const y = ((index % 11) / 10 - 0.5) * 1.7
          return (
            <group key={index} position={[Math.cos(angle) * 0.43, y, Math.sin(angle) * 0.43]}>
              <mesh rotation={[Math.PI / 2, angle + Math.PI / 2, 0]}>
                <capsuleGeometry args={[0.008, 0.12 + (index % 3) * 0.035, 3, 5]} />
                <meshStandardMaterial color="#9ce9dc" roughness={0.5} />
              </mesh>
            </group>
          )
        })}
        {flagella.map((curve, index) => (
          <mesh key={index}>
            <tubeGeometry args={[curve, 40, 0.009, 5, false]} />
            <meshStandardMaterial color="#8ccbc7" roughness={0.4} />
          </mesh>
        ))}
      </group>
    </group>
  )
}

export function BacterialEvolutionScene({
  profile,
  before,
  animate,
  anatomy,
}: {
  profile: ResistanceProfile
  before: ResistanceProfile
  animate: boolean
  anatomy: boolean
}) {
  return (
    <div className={styles.scene} data-profile={profile.join('')}>
      <SceneFrame
        animated={animate}
        rotateByDefault={false}
        camera={{ position: [0, 0, anatomy ? 8 : 5.5], fov: 40 }}
        label={`Illustrative E. coli cell. Membrane colors encode the recorded resistance profile ${profile.join('')}, not bacterial numbers or physical mutation sites.${anatomy ? ' Urinary tract shown for anatomical context.' : ''}`}
        fallback={
          <div className={styles.fallback}>
            <strong>3D view unavailable</strong>
            <span>Use the timeline to follow the recorded resistance changes.</span>
          </div>
        }
      >
        {() => (
          <>
            {anatomy ? (
              <group position={[-1.25, 0, -0.4]} scale={0.85}>
                <UrinaryTractModel />
              </group>
            ) : null}
            <Bacterium profile={profile} before={before} animate={animate} anatomy={anatomy} />
            <pointLight position={[-2, 2, 3]} color="#a4d8ff" intensity={14} />
            <pointLight position={[2, -1, -1]} color="#83b2ce" intensity={8} />
          </>
        )}
      </SceneFrame>
    </div>
  )
}

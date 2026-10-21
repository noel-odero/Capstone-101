import { useEffect, useMemo, useRef } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import { Color, Object3D, type InstancedMesh } from 'three'
import { seededRandom } from './geometry'
import { SceneFrame } from './SceneFrame'
import { prefersReducedMotion } from './sceneSupport'
import styles from './clearance.module.css'
import { UrinaryTractModel } from './UrinaryTractModel'

const PARTICLES = 48

/** Educational visual particles, not CFU or a bacterial-load estimate. */
function Bacteria({ progress }: { progress: number }) {
  const mesh = useRef<InstancedMesh>(null)
  const debris = useRef<InstancedMesh>(null)
  const animatedProgress = useRef(progress)
  const invalidate = useThree((state) => state.invalidate)
  const reduced = prefersReducedMotion()
  const helper = useMemo(() => new Object3D(), [])
  const color = useMemo(() => new Color(), [])
  const particles = useMemo(() => {
    const random = seededRandom(101)
    return Array.from({ length: PARTICLES }, (_, index) => {
      const region = index % 3
      return {
        x:
          (region === 0 ? -1.02 : region === 1 ? 1.02 : 0) +
          (random() - 0.5) * (region === 2 ? 0.95 : 0.8),
        y: (region === 2 ? -1.35 : 1.2) + (random() - 0.5) * (region === 2 ? 0.6 : 1.2),
        z: (random() - 0.5) * 0.55 + 0.28,
        phase: random() * Math.PI * 2,
        rotation: random() * Math.PI,
        // Interleave clearance across all three organs instead of clearing one at a time.
        threshold: ((index * 19) % PARTICLES) / PARTICLES,
      }
    })
  }, [])
  useEffect(() => {
    invalidate()
  }, [progress, invalidate])
  useFrame((state, delta) => {
    if (!mesh.current || !debris.current) return
    animatedProgress.current = reduced
      ? progress
      : animatedProgress.current +
        (progress - animatedProgress.current) * (1 - Math.exp(-delta * 5))
    if (Math.abs(animatedProgress.current - progress) < 0.002) animatedProgress.current = progress
    const current = animatedProgress.current
    const time = reduced ? 0 : state.clock.elapsedTime
    particles.forEach((particle, index) => {
      const dissolve = Math.max(0, Math.min(1, (current - particle.threshold) * PARTICLES))
      const size = Math.max(0.0001, 1 - dissolve)
      helper.position.set(
        particle.x + Math.sin(time * 0.65 + particle.phase) * 0.035,
        particle.y + Math.cos(time * 0.8 + particle.phase) * 0.04,
        particle.z,
      )
      helper.rotation.set(
        0.4,
        particle.phase,
        particle.rotation + Math.sin(time * 0.4 + particle.phase) * 0.16,
      )
      helper.scale.setScalar(size)
      helper.updateMatrix()
      mesh.current!.setMatrixAt(index, helper.matrix)
      color.set(dissolve > 0 ? '#79e8d2' : '#ffad72')
      mesh.current!.setColorAt(index, color)
      // A small outward sparkle accompanies each bacterium dissolving.
      helper.position.x += Math.cos(particle.phase) * dissolve * 0.35
      helper.position.y += Math.sin(particle.phase) * dissolve * 0.35
      helper.scale.setScalar(Math.sin(dissolve * Math.PI) * 0.065)
      helper.updateMatrix()
      debris.current!.setMatrixAt(index, helper.matrix)
    })
    mesh.current.instanceMatrix.needsUpdate = true
    if (mesh.current.instanceColor) mesh.current.instanceColor.needsUpdate = true
    debris.current.instanceMatrix.needsUpdate = true
  })
  return (
    <>
      <instancedMesh ref={mesh} args={[undefined, undefined, PARTICLES]} frustumCulled={false}>
        <capsuleGeometry args={[0.03, 0.08, 5, 10]} />
        <meshStandardMaterial
          color="#ffffff"
          emissive="#db682e"
          emissiveIntensity={0.65}
          roughness={0.35}
        />
      </instancedMesh>
      <instancedMesh ref={debris} args={[undefined, undefined, PARTICLES]} frustumCulled={false}>
        <sphereGeometry args={[1, 6, 6]} />
        <meshBasicMaterial color="#9fffe5" />
      </instancedMesh>
    </>
  )
}

export function BacteriaClearanceScene({ step, horizon }: { step: number; horizon: number }) {
  const progress = Math.min(1, Math.max(0, step / Math.max(1, horizon)))
  const remaining = Math.round(PARTICLES * (1 - progress))
  return (
    <div className={styles['scene']} data-step={step} data-visual-particles={remaining}>
      <SceneFrame
        animated
        rotateByDefault={false}
        camera={{ position: [0, 0, 7.8], fov: 38 }}
        label={`Interactive 3D urinary tract. Illustrative bacteria clearance, step ${step} of ${horizon}. ${remaining} visual bacteria remaining. Drag to rotate; scroll to zoom.`}
        fallback={
          <div className={styles['fallback']}>
            <strong>3D view unavailable</strong>
            <span>
              {remaining} of {PARTICLES} illustrative bacteria remain at step {step}.
            </span>
            <small>Your browser needs WebGL to display the interactive scene.</small>
          </div>
        }
      >
        {() => (
          <>
            <UrinaryTractModel />
            <Bacteria progress={progress} />
            <pointLight position={[0, 0, 3]} color="#88ddff" intensity={12} />
          </>
        )}
      </SceneFrame>
      <span className={styles['hint']}>Drag to rotate · Scroll to zoom</span>
    </div>
  )
}

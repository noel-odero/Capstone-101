import { Pill } from './Pill'
import { EcoliBody } from './EcoliBody'
import { EcoliIllustration } from './EcoliIllustration'
import { SceneFrame } from './SceneFrame'
import { SCENE_COLORS } from './sceneColors'

function Bubble({ position, size }: { position: [number, number, number]; size: number }) {
  return (
    <mesh position={position}>
      <sphereGeometry args={[size, 24, 16]} />
      <meshStandardMaterial color={SCENE_COLORS.bubble} transparent opacity={0.4} roughness={0.15} />
    </mesh>
  )
}

/**
 * The landing-page visual: an indigo E. coli rod with a smaller cell, antibiotic capsules and pale bubbles. It is
 * decorative and says nothing about any result. Rotation is slow and stops under reduced motion.
 */
export function EcoliHeroScene() {
  return (
    <SceneFrame
      controls="rotate-only"
      label="Decorative 3D illustration of an E. coli bacterium with antibiotic capsules. Drag to rotate."
      fallback={<EcoliIllustration />}
      camera={{ position: [0, 0.2, 7.5], fov: 38 }}
    >
      {() => (
        <group>
          <group position={[0.7, 0, 0]} rotation={[0.25, 0.4, 0.85]} scale={1.15}>
            <EcoliBody />
          </group>
          <group position={[-2.5, 0.5, -0.8]} rotation={[0.2, 0.5, -0.5]} scale={0.5}>
            <EcoliBody color={SCENE_COLORS.smallBacterium} bumpColor="#b9a4ff" seed={21} bumpCount={120} />
          </group>
          <Pill position={[-0.9, -1.9, 1.1]} rotation={[0.4, 0.2, 0.7]} halves={[SCENE_COLORS.capsuleCyan, SCENE_COLORS.capsuleCyanLight]} />
          <Pill position={[-1.9, 1.9, 0.6]} rotation={[0.3, 0.5, -0.6]} halves={[SCENE_COLORS.capsuleBlue, SCENE_COLORS.capsuleCyanLight]} scale={0.9} />
          <Pill position={[2.9, -1.9, 0.9]} rotation={[0.2, 0.3, 0.5]} halves={[SCENE_COLORS.capsuleViolet, SCENE_COLORS.capsuleVioletLight]} scale={1.05} />
          <Bubble position={[2.7, 2, -0.5]} size={0.42} />
          <Bubble position={[-3.1, -0.9, 0.3]} size={0.18} />
          <Bubble position={[3.4, 0.3, 0.8]} size={0.14} />
          <Bubble position={[-0.2, 2.5, -1.2]} size={0.22} />
        </group>
      )}
    </SceneFrame>
  )
}

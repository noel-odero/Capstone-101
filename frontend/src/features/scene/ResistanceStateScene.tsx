import { Html, Line } from '@react-three/drei'
import type { AntibioticEntry } from '@/domain/antibiotics'
import { RESISTANT } from '@/domain/profile'
import type { ResistanceProfile } from '@/domain/types'
import { EcoliBody } from './EcoliBody'
import { markerPosition, type Point3 } from './geometry'
import { Pill } from './Pill'
import { ResistanceStateFallback } from './ResistanceStateFallback'
import { SceneFrame } from './SceneFrame'
import { SCENE_COLORS } from './sceneColors'
import styles from './scene.module.css'

const RING_RADIUS = 2.45

interface MarkerProps {
  position: Point3
  resistant: boolean
  changed: boolean
  selectedAction: boolean
  label: string
}

/** One antibiotic. Resistant is a red diamond marked R; susceptible is a green sphere marked S; a ring marks a change. */
function Marker({ position, resistant, changed, selectedAction, label }: MarkerProps) {
  const color = resistant ? SCENE_COLORS.resistant : SCENE_COLORS.susceptible
  const glow = resistant ? SCENE_COLORS.resistantGlow : SCENE_COLORS.susceptibleGlow
  return (
    <group position={[position[0], position[1], position[2]]}>
      <mesh>
        {resistant ? <octahedronGeometry args={[0.38]} /> : <sphereGeometry args={[0.32, 32, 20]} />}
        <meshStandardMaterial color={color} emissive={glow} emissiveIntensity={0.7} roughness={0.35} />
      </mesh>
      <mesh scale={1.9}>
        <sphereGeometry args={[0.32, 20, 14]} />
        <meshBasicMaterial color={glow} transparent opacity={0.16} depthWrite={false} />
      </mesh>
      {changed ? (
        <mesh>
          <torusGeometry args={[0.58, 0.035, 10, 40]} />
          <meshBasicMaterial color={SCENE_COLORS.changed} />
        </mesh>
      ) : null}
      {selectedAction ? <Pill position={[0.62, 0.42, 0.2]} rotation={[0, 0, -0.7]} halves={[SCENE_COLORS.capsuleCyan, SCENE_COLORS.capsuleCyanLight]} scale={0.55} /> : null}
      <Html center position={[0, -0.78, 0]} zIndexRange={[10, 0]}>
        <span className={styles['label']}>
          {label} {resistant ? 'R' : 'S'}
        </span>
      </Html>
    </group>
  )
}

export interface ResistanceStateSceneProps {
  entries: readonly AntibioticEntry[]
  profile: ResistanceProfile
  /** The profile one step earlier; positions that differ are ringed. */
  previousProfile?: ResistanceProfile | null
  /** The antibiotic selected at this step, shown as a capsule beside its marker. */
  selectedActionIndex?: number | null
}

/**
 * Interactive 3D view of one simulated resistance state: an E. coli rod linked to seven markers in the backend's
 * antibiotic order. It shows only the profile it is given, so it changes when the selected step changes. It does not model
 * bacterial numbers, clearance or any organ.
 */
export function ResistanceStateScene({ entries, profile, previousProfile = null, selectedActionIndex = null }: ResistanceStateSceneProps) {
  const changed = new Set<number>()
  if (previousProfile) {
    profile.forEach((state, index) => {
      if (state !== previousProfile[index]) {
        changed.add(index)
      }
    })
  }

  const summary = `Resistance state of ${entries.length} antibiotics: ${entries.map((entry) => `${entry.displayName} ${profile[entry.index] === RESISTANT ? 'resistant' : 'susceptible'}`).join(', ')}.`

  return (
    <SceneFrame
      label={`${summary} Drag to rotate.`}
      background={SCENE_COLORS.panel}
      fallback={<ResistanceStateFallback entries={entries} profile={profile} changed={changed} selectedActionIndex={selectedActionIndex} />}
      camera={{ position: [0, 0, 8.2], fov: 40 }}
      rotateByDefault={false}
    >
      {() => (
        <group>
          <group rotation={[0.2, 0.3, 1.1]} scale={0.62}>
            <EcoliBody />
          </group>
          {entries.map((entry) => {
            const position = markerPosition(entry.index, entries.length, RING_RADIUS)
            return (
              <group key={entry.actionId}>
                <Line points={[[0, 0, 0], [position[0], position[1], position[2]]]} color={SCENE_COLORS.link} lineWidth={1} transparent opacity={0.45} />
                <Marker
                  position={position}
                  resistant={profile[entry.index] === RESISTANT}
                  changed={changed.has(entry.index)}
                  selectedAction={selectedActionIndex === entry.index}
                  label={entry.abbreviation ?? entry.displayName}
                />
              </group>
            )
          })}
        </group>
      )}
    </SceneFrame>
  )
}

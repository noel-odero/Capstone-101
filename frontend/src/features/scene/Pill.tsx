interface PillProps {
  position: [number, number, number]
  rotation: [number, number, number]
  halves: readonly [string, string]
  scale?: number
}

/** A two-tone antibiotic capsule built from cylinders and hemispheres. */
export function Pill({ position, rotation, halves, scale = 1 }: PillProps) {
  const radius = 0.2
  return (
    <group position={position} rotation={rotation} scale={scale}>
      <mesh position={[0, -0.18, 0]}>
        <cylinderGeometry args={[radius, radius, 0.36, 24]} />
        <meshStandardMaterial color={halves[0]} roughness={0.3} />
      </mesh>
      <mesh position={[0, -0.36, 0]}>
        <sphereGeometry args={[radius, 24, 12, 0, Math.PI * 2, Math.PI / 2, Math.PI / 2]} />
        <meshStandardMaterial color={halves[0]} roughness={0.3} />
      </mesh>
      <mesh position={[0, 0.18, 0]}>
        <cylinderGeometry args={[radius, radius, 0.36, 24]} />
        <meshStandardMaterial color={halves[1]} roughness={0.3} />
      </mesh>
      <mesh position={[0, 0.36, 0]}>
        <sphereGeometry args={[radius, 24, 12, 0, Math.PI * 2, 0, Math.PI / 2]} />
        <meshStandardMaterial color={halves[1]} roughness={0.3} />
      </mesh>
    </group>
  )
}

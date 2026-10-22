import { Environment, Lightformer } from '@react-three/drei'
import { useEffect, useMemo } from 'react'
import {
  AdditiveBlending,
  BackSide,
  CatmullRomCurve3,
  Color,
  Float32BufferAttribute,
  SphereGeometry,
  Vector3,
} from 'three'

type Point = [number, number, number]

function Vessel({
  points,
  radius = 0.025,
  color = '#f6cc78',
  glow = 0.45,
}: {
  points: Point[]
  radius?: number
  color?: string
  glow?: number
}) {
  const curve = useMemo(
    () => new CatmullRomCurve3(points.map((point) => new Vector3(...point))),
    [points],
  )
  return (
    <mesh>
      <tubeGeometry args={[curve, 36, radius, 8, false]} />
      <meshStandardMaterial
        color={color}
        emissive={color}
        emissiveIntensity={glow}
        roughness={0.28}
        metalness={0.12}
      />
    </mesh>
  )
}

const rimVertex = `varying vec3 vNormal; varying vec3 vView; void main(){vec4 p=modelViewMatrix*vec4(position,1.); vNormal=normalize(normalMatrix*normal); vView=normalize(-p.xyz); gl_Position=projectionMatrix*p;}`
const rimFragment = `varying vec3 vNormal; varying vec3 vView; uniform vec3 tint; void main(){float rim=pow(1.-abs(dot(normalize(vNormal),normalize(vView))),2.8); gl_FragColor=vec4(tint,rim*.32);}`

function RenalPelvis({ cool }: { cool: boolean }) {
  return (
    <group>
      <mesh position={[-0.22, -0.08, 0.1]} rotation={[0, 0, -0.3]} scale={[0.09, 0.23, 0.12]}>
        <sphereGeometry args={[1, 24, 20]} />
        <meshStandardMaterial
          color={cool ? '#b9ed7a' : '#ffc65c'}
          emissive={cool ? '#6ddc43' : '#fba92d'}
          emissiveIntensity={0.5}
          roughness={0.25}
        />
      </mesh>
      {[-0.55, -0.28, 0, 0.28, 0.53].map((y, index) => (
        <group key={y}>
          <Vessel
            points={[
              [-0.3, -0.12, 0.1],
              [-0.08, y * 0.6, 0.13],
              [0.18, y, 0.11],
            ]}
            radius={0.028}
            color={cool ? '#b7e87d' : '#ffd28a'}
          />
          <Vessel
            points={[
              [0.08, y * 0.75, 0.12],
              [0.28, y + 0.08, 0.12],
              [0.39, y + 0.14, 0.08],
            ]}
            radius={0.012}
            color="#f7c1a1"
            glow={0.15}
          />
          <Vessel
            points={[
              [-0.19, y * 0.5, 0.14],
              [0.02, y - 0.15, 0.21],
              [0.22, y - 0.2, 0.18],
            ]}
            radius={0.009}
            color={index % 2 ? '#bc7a86' : '#7fa9d5'}
            glow={0.1}
          />
        </group>
      ))}
    </group>
  )
}

function Kidney({ side }: { side: number }) {
  const geometry = useMemo(() => {
    const result = new SphereGeometry(1, 64, 48)
    const positions = result.getAttribute('position')
    for (let index = 0; index < positions.count; index++) {
      const x = positions.getX(index),
        y = positions.getY(index),
        z = positions.getZ(index)
      const indent = Math.max(0, -x) * 0.72 * Math.exp(-y * y * 5.5)
      const lobe = 1 + 0.025 * Math.sin(y * 15 + z * 4)
      positions.setXYZ(index, (x + indent) * 0.58 * lobe, y * 0.86, z * 0.43 * lobe)
    }
    result.computeVertexNormals()
    const colors = []
    const upper = new Color('#708897'),
      lower = new Color('#884d68'),
      tint = new Color()
    for (let index = 0; index < positions.count; index++) {
      const y = positions.getY(index),
        x = positions.getX(index)
      tint.copy(upper).lerp(lower, Math.max(0, Math.min(1, 0.5 - y)))
      tint.multiplyScalar(0.9 + 0.1 * Math.sin(y * 21 + x * 17))
      colors.push(tint.r, tint.g, tint.b)
    }
    result.setAttribute('color', new Float32BufferAttribute(colors, 3))
    return result
  }, [])
  useEffect(() => () => geometry.dispose(), [geometry])
  const cool = side === -1
  return (
    <group
      position={[side * 1.02, 1.12, 0]}
      rotation={[0, side * -0.18, side * -0.18]}
      scale={[side, 1, 1]}
    >
      {/* Medullary lobes beneath the transparent renal capsule. */}
      {[-0.44, -0.14, 0.17, 0.44].map((y) => (
        <mesh
          key={y}
          position={[0.1, y, -0.08]}
          rotation={[0, 0, -y * 0.5]}
          scale={[0.27, 0.24, 0.2]}
        >
          <sphereGeometry args={[1, 32, 24]} />
          <meshPhysicalMaterial
            color={y < 0 ? '#ad5a73' : '#6e81a2'}
            roughness={0.38}
            clearcoat={0.65}
            transparent
            opacity={0.55}
          />
        </mesh>
      ))}
      <RenalPelvis cool={cool} />
      <mesh geometry={geometry}>
        <meshPhysicalMaterial
          color="#ffffff"
          vertexColors
          transparent
          opacity={0.76}
          roughness={0.26}
          metalness={0.12}
          clearcoat={1}
          clearcoatRoughness={0.3}
          depthWrite={false}
          specularIntensity={1.4}
        />
      </mesh>
      <mesh geometry={geometry} scale={1.015}>
        <shaderMaterial
          vertexShader={rimVertex}
          fragmentShader={rimFragment}
          uniforms={{ tint: { value: new Color('#b0d9e9') } }}
          transparent
          depthWrite={false}
          side={BackSide}
          blending={AdditiveBlending}
        />
      </mesh>
      {/* Fine surface vessels, visible through the capsule, follow its curved face. */}
      {[-0.36, -0.05, 0.27, 0.5].map((y, index) => (
        <Vessel
          key={y}
          points={[
            [0.33, y - 0.12, 0.32],
            [0.18, y, 0.38],
            [-0.03, y + 0.11, 0.34],
            [-0.14, y + 0.2, 0.25],
          ]}
          radius={0.004}
          color={index % 2 ? '#c797a5' : '#8eb2c7'}
          glow={0.05}
        />
      ))}
    </group>
  )
}

function Ureter({ side }: { side: number }) {
  const points: Point[] = [
    [side * 0.72, 1.02, 0.12],
    [side * 0.62, 0.59, 0.15],
    [side * 0.61, -0.08, 0.17],
    [side * 0.48, -0.68, 0.15],
    [side * 0.27, -1.12, 0.13],
  ]
  return (
    <group>
      <Vessel
        points={points}
        radius={0.053}
        color={side === -1 ? '#b5c264' : '#df8a38'}
        glow={0.3}
      />
      <Vessel
        points={points.map(([x, y, z]) => [x - 0.013, y, z + 0.043])}
        radius={0.012}
        color="#fff4bd"
        glow={0.55}
      />
      <Vessel
        points={points.slice(0, 3)}
        radius={0.026}
        color={side === -1 ? '#81e76a' : '#ffb956'}
        glow={0.8}
      />
    </group>
  )
}

function Bladder() {
  const geometry = useMemo(() => {
    const result = new SphereGeometry(1, 56, 40)
    const positions = result.getAttribute('position')
    for (let i = 0; i < positions.count; i++) {
      const x = positions.getX(i),
        y = positions.getY(i),
        z = positions.getZ(i)
      const taper = y < 0 ? 1 + y * 0.3 : 1
      positions.setXYZ(i, x * 0.63 * taper, y * 0.5, z * 0.42 * taper)
    }
    result.computeVertexNormals()
    return result
  }, [])
  useEffect(() => () => geometry.dispose(), [geometry])
  return (
    <group position={[0, -1.27, 0.1]}>
      <mesh geometry={geometry}>
        <meshPhysicalMaterial
          color="#7fe69b"
          transparent
          opacity={0.42}
          clearcoat={1}
          roughness={0.16}
          depthWrite={false}
        />
      </mesh>
      <mesh position={[0, -0.03, 0]} scale={[0.48, 0.35, 0.28]}>
        <sphereGeometry args={[1, 36, 28]} />
        <meshPhysicalMaterial
          color="#57ba70"
          emissive="#44b647"
          emissiveIntensity={0.3}
          roughness={0.38}
          transparent
          opacity={0.45}
        />
      </mesh>
      <mesh position={[0.08, -0.07, 0.18]} scale={[0.15, 0.19, 0.09]}>
        <sphereGeometry args={[1, 24, 20]} />
        <meshStandardMaterial
          color="#d8d852"
          emissive="#a5a72c"
          emissiveIntensity={0.35}
          transparent
          opacity={0.56}
          depthWrite={false}
        />
      </mesh>
      {[-1, 1].map((side) => (
        <group key={side}>
          <Vessel
            points={[
              [0, -0.35, 0.24],
              [side * 0.11, -0.12, 0.33],
              [side * 0.34, 0.08, 0.3],
              [side * 0.42, 0.23, 0.15],
            ]}
            radius={0.009}
            color="#93db69"
            glow={0.45}
          />
          <Vessel
            points={[
              [side * 0.13, -0.13, 0.33],
              [side * 0.31, -0.08, 0.33],
              [side * 0.45, 0.04, 0.23],
            ]}
            radius={0.006}
            color="#b4df6f"
          />
        </group>
      ))}
      <mesh position={[0, -0.55, -0.02]}>
        <capsuleGeometry args={[0.09, 0.35, 12, 20]} />
        <meshPhysicalMaterial
          color="#5bd698"
          emissive="#169e70"
          emissiveIntensity={0.35}
          clearcoat={1}
          roughness={0.25}
          transparent
          opacity={0.75}
        />
      </mesh>
      <mesh geometry={geometry} scale={1.02}>
        <shaderMaterial
          vertexShader={rimVertex}
          fragmentShader={rimFragment}
          uniforms={{ tint: { value: new Color('#8af8ba') } }}
          transparent
          depthWrite={false}
          side={BackSide}
          blending={AdditiveBlending}
        />
      </mesh>
    </group>
  )
}

/** Sculpted layered anatomy with real depth; no image planes or wireframe overlays. */
export function UrinaryTractModel() {
  return (
    <>
      <Environment resolution={64} frames={1}>
        <Lightformer position={[-3, 3, 4]} scale={[2, 5, 1]} intensity={2} color="#e2f2ff" />
        <Lightformer
          position={[4, 1, 2]}
          rotation={[0, -Math.PI / 3, 0]}
          scale={[2, 4, 1]}
          intensity={1.8}
          color="#9ed6ee"
        />
        <Lightformer
          position={[0, 4, -2]}
          rotation={[Math.PI / 2, 0, 0]}
          scale={[4, 3, 1]}
          intensity={1}
          color="#d3e2ed"
        />
      </Environment>
      <Kidney side={-1} />
      <Kidney side={1} />
      <Ureter side={-1} />
      <Ureter side={1} />
      <Bladder />
    </>
  )
}

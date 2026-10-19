import { OrbitControls } from '@react-three/drei'
import { Canvas, useThree } from '@react-three/fiber'
import { Pause, Play, RotateCcw, RotateCw, Undo2, ZoomIn, ZoomOut } from 'lucide-react'
import { Component, useCallback, useEffect, useMemo, useRef, useState, type ComponentRef, type ReactNode } from 'react'
import type { Vector3 } from 'three'
import { Button } from '@/components/ui/Button'
import { MAX_DISTANCE, MIN_DISTANCE, orbitedPosition, zoomedPosition } from './sceneCamera'
import { detectWebGl, prefersReducedMotion } from './sceneSupport'
import styles from './scene.module.css'

function ContextLossGuard({ onLost }: { onLost: () => void }) {
  const element = useThree((state) => state.gl.domElement)
  useEffect(() => {
    const handler = (event: Event) => {
      event.preventDefault()
      onLost()
    }
    element.addEventListener('webglcontextlost', handler)
    return () => element.removeEventListener('webglcontextlost', handler)
  }, [element, onLost])
  return null
}

class SceneErrorBoundary extends Component<{ fallback: ReactNode; children: ReactNode }, { failed: boolean }> {
  override state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  override render() {
    return this.state.failed ? this.props.fallback : this.props.children
  }
}

export interface SceneFrameProps {
  /** Accessible description of what the scene shows; the canvas itself is not readable by assistive technology. */
  label: string
  /** Shown instead of the canvas when WebGL is unavailable, fails, or is lost. */
  fallback: ReactNode
  /** Scene contents; `autoRotate` reflects the user's rotation setting. */
  children: (state: { autoRotate: boolean }) => ReactNode
  controls?: 'full' | 'rotate-only'
  className?: string
  background?: string
  camera?: { position: [number, number, number]; fov: number }
  /** Rotation starts on unless the user prefers reduced motion. */
  rotateByDefault?: boolean
}

/**
 * One place for everything a WebGL scene needs to be safe: capability detection, an error boundary, context-loss handling,
 * reduced-motion defaults, bounded zoom, keyboard-operable controls and a fallback. R3F disposes the renderer, geometries
 * and materials on unmount; the one listener added here is removed in its effect cleanup.
 */
export function SceneFrame({
  label,
  fallback,
  children,
  controls = 'full',
  className,
  background,
  camera = { position: [0, 0.4, 7], fov: 40 },
  rotateByDefault = true,
}: SceneFrameProps) {
  const controlsRef = useRef<ComponentRef<typeof OrbitControls>>(null)
  const webGlAvailable = useMemo(() => detectWebGl(), [])
  const [autoRotate, setAutoRotate] = useState(() => rotateByDefault && !prefersReducedMotion())
  const [ready, setReady] = useState(false)
  const [contextLost, setContextLost] = useState(false)
  const onLost = useCallback(() => setContextLost(true), [])

  if (!webGlAvailable || contextLost) {
    return <>{fallback}</>
  }

  const moveCamera = (compute: (position: Vector3, target: Vector3) => Vector3) => {
    const current = controlsRef.current
    if (current) {
      current.object.position.copy(compute(current.object.position, current.target))
      current.update()
    }
  }

  return (
    <div className={styles['frame']}>
      <div className={`${styles['canvasBox']} ${className ?? ''}`} role="img" aria-label={label} style={background ? { background } : undefined}>
        {ready ? null : <p className={styles['loading']}>Preparing 3D view&hellip;</p>}
        <SceneErrorBoundary fallback={fallback}>
          <Canvas
            frameloop={autoRotate ? 'always' : 'demand'}
            dpr={[1, 2]}
            camera={camera}
            gl={{ antialias: true, alpha: true, powerPreference: 'low-power' }}
            onCreated={() => setReady(true)}
          >
            <ambientLight intensity={0.9} />
            <directionalLight position={[3, 4, 5]} intensity={1.8} />
            <directionalLight position={[-4, -2, -3]} color="#8aa4ff" intensity={0.9} />
            <pointLight position={[0, 2, -4]} color="#c4b5fd" intensity={30} />
            {children({ autoRotate })}
            <OrbitControls
              ref={controlsRef}
              makeDefault
              enablePan={false}
              enableZoom={controls === 'full'}
              enableDamping
              minDistance={MIN_DISTANCE}
              maxDistance={MAX_DISTANCE}
              autoRotate={autoRotate}
              autoRotateSpeed={0.8}
            />
            <ContextLossGuard onLost={onLost} />
          </Canvas>
        </SceneErrorBoundary>
      </div>
      {controls === 'full' ? (
        <div className={styles['toolbar']} role="toolbar" aria-label="3D view controls">
          <Button variant="secondary" size="sm" onClick={() => moveCamera((p, t) => orbitedPosition(p, t, Math.PI / 8))} aria-label="Rotate left">
            <RotateCcw size={16} aria-hidden="true" />
          </Button>
          <Button variant="secondary" size="sm" onClick={() => moveCamera((p, t) => orbitedPosition(p, t, -Math.PI / 8))} aria-label="Rotate right">
            <RotateCw size={16} aria-hidden="true" />
          </Button>
          <Button variant="secondary" size="sm" onClick={() => moveCamera((p, t) => zoomedPosition(p, t, 0.8))} aria-label="Zoom in">
            <ZoomIn size={16} aria-hidden="true" />
          </Button>
          <Button variant="secondary" size="sm" onClick={() => moveCamera((p, t) => zoomedPosition(p, t, 1.25))} aria-label="Zoom out">
            <ZoomOut size={16} aria-hidden="true" />
          </Button>
          <Button variant="secondary" size="sm" onClick={() => controlsRef.current?.reset()}>
            <Undo2 size={16} aria-hidden="true" /> Reset
          </Button>
          <Button variant="secondary" size="sm" aria-pressed={autoRotate} onClick={() => setAutoRotate((current) => !current)}>
            {autoRotate ? <Pause size={16} aria-hidden="true" /> : <Play size={16} aria-hidden="true" />}
            {autoRotate ? 'Pause' : 'Rotate'}
          </Button>
        </div>
      ) : null}
    </div>
  )
}

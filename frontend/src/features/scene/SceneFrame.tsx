import { OrbitControls } from '@react-three/drei'
import { Canvas, useThree } from '@react-three/fiber'
import { Component, useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { MAX_DISTANCE, MIN_DISTANCE } from './sceneCamera'
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

class SceneErrorBoundary extends Component<
  { fallback: ReactNode; children: ReactNode },
  { failed: boolean }
> {
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
  /** Scene contents; `autoRotate` is true when the scene turns by itself. */
  children: (state: { autoRotate: boolean }) => ReactNode
  /** `full` also allows zooming with the wheel or a pinch. */
  controls?: 'full' | 'rotate-only'
  className?: string
  background?: string
  camera?: { position: [number, number, number]; fov: number }
  /** Rotation starts on unless the user prefers reduced motion. */
  rotateByDefault?: boolean
  /** Keep rendering for animated scene contents, independently of camera rotation. */
  animated?: boolean
}

/**
 * One place for everything a WebGL scene needs to be safe: capability detection, an error boundary, context-loss handling,
 * reduced-motion defaults, bounded zoom and a fallback. Dragging rotates the view; there are no on-screen buttons. R3F disposes
 * the renderer, geometries and materials on unmount; the one listener added here is removed in its effect cleanup.
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
  animated = false,
}: SceneFrameProps) {
  const webGlAvailable = useMemo(() => detectWebGl(), [])
  const [autoRotate] = useState(() => rotateByDefault && !prefersReducedMotion())
  const [ready, setReady] = useState(false)
  const [contextLost, setContextLost] = useState(false)
  const onLost = useCallback(() => setContextLost(true), [])

  if (!webGlAvailable || contextLost) {
    return <>{fallback}</>
  }

  return (
    <div className={styles['frame']}>
      <div
        className={`${styles['canvasBox']} ${className ?? ''}`}
        role="img"
        aria-label={label}
        style={background ? { background } : undefined}
      >
        {ready ? null : <p className={styles['loading']}>Preparing 3D view&hellip;</p>}
        <SceneErrorBoundary fallback={fallback}>
          <Canvas
            frameloop={autoRotate || (animated && !prefersReducedMotion()) ? 'always' : 'demand'}
            dpr={[1, 2]}
            camera={camera}
            gl={{ antialias: true, alpha: true, powerPreference: 'low-power' }}
            onCreated={() => setReady(true)}
          >
            <ambientLight intensity={0.9} />
            <directionalLight position={[3, 4, 5]} intensity={1.8} />
            <directionalLight position={[-4, -2, -3]} color="#ffffff" intensity={0.9} />
            <pointLight position={[0, 2, -4]} color="#ffffff" intensity={30} />
            {children({ autoRotate })}
            <OrbitControls
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
    </div>
  )
}

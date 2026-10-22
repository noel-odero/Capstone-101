import styles from './scene.module.css'
import { SCENE_COLORS } from './sceneColors'

/** Static stand-in for the 3D hero (no WebGL, tests, print). Same palette and composition as the live scene. */
export function EcoliIllustration({ title = 'Illustration of an E. coli bacterium surrounded by antibiotic capsules' }: { title?: string }) {
  return (
    <div className={styles['fallback']}>
      <svg className={styles['fallbackSvg']} viewBox="0 0 420 300" role="img" aria-label={title}>
        <title>{title}</title>
        <g fill={SCENE_COLORS.bubble} opacity="0.45">
          <circle cx="330" cy="40" r="22" />
          <circle cx="90" cy="64" r="14" />
          <circle cx="380" cy="190" r="12" />
          <circle cx="40" cy="190" r="10" />
        </g>
        <g transform="rotate(-38 235 150)">
          <rect x="105" y="100" width="260" height="100" rx="50" fill={SCENE_COLORS.bacterium} />
          <rect x="105" y="100" width="260" height="100" rx="50" fill="none" stroke={SCENE_COLORS.bacteriumRim} strokeOpacity="0.5" strokeWidth="3" />
          <g fill={SCENE_COLORS.bacteriumBump} opacity="0.7">
            {Array.from({ length: 28 }, (_, index) => (
              <circle key={index} cx={130 + ((index * 53) % 220)} cy={112 + ((index * 37) % 76)} r="3.5" />
            ))}
          </g>
        </g>
        <ellipse cx="82" cy="150" rx="26" ry="42" fill={SCENE_COLORS.smallBacterium} transform="rotate(-12 82 150)" />
        <g transform="rotate(-35 150 230)">
          <rect x="122" y="214" width="28" height="32" rx="14" fill={SCENE_COLORS.capsuleCyan} />
          <rect x="150" y="214" width="28" height="32" rx="14" fill={SCENE_COLORS.capsuleCyanLight} />
        </g>
        <g transform="rotate(30 340 240)">
          <rect x="312" y="226" width="28" height="32" rx="14" fill={SCENE_COLORS.capsuleViolet} />
          <rect x="340" y="226" width="28" height="32" rx="14" fill={SCENE_COLORS.capsuleVioletLight} />
        </g>
        <rect x="150" y="30" width="26" height="50" rx="13" fill={SCENE_COLORS.capsuleBlue} transform="rotate(25 163 55)" />
      </svg>
    </div>
  )
}

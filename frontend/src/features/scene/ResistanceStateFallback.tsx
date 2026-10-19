import type { AntibioticEntry } from '@/domain/antibiotics'
import { RESISTANT } from '@/domain/profile'
import type { ResistanceProfile } from '@/domain/types'
import { markerPosition } from './geometry'
import { SCENE_COLORS } from './sceneColors'

export interface ResistanceStateFallbackProps {
  entries: readonly AntibioticEntry[]
  profile: ResistanceProfile
  changed: ReadonlySet<number>
  selectedActionIndex: number | null
}

const RING = 105

/**
 * The same seven-marker ring as the 3D scene, drawn flat. It is the view when WebGL is unavailable and the
 * text-equivalent of the 3D state: each marker is a circle (susceptible) or a diamond (resistant) with an S or R.
 */
export function ResistanceStateFallback({ entries, profile, changed, selectedActionIndex }: ResistanceStateFallbackProps) {
  return (
    <svg viewBox="-150 -150 300 300" role="img" width="100%" height="100%" aria-label="Resistance state of the seven antibiotics" style={{ background: SCENE_COLORS.panel, borderRadius: 'var(--radius-lg)', minHeight: '16rem' }}>
      <ellipse cx="0" cy="0" rx="46" ry="24" transform="rotate(-35)" fill={SCENE_COLORS.bacterium} />
      {entries.map((entry) => {
        const [x, y] = markerPosition(entry.index, entries.length, RING)
        const resistant = profile[entry.index] === RESISTANT
        const color = resistant ? SCENE_COLORS.resistant : SCENE_COLORS.susceptible
        return (
          <g key={entry.actionId}>
            <line x1="0" y1="0" x2={x} y2={-y} stroke={SCENE_COLORS.link} strokeOpacity="0.5" />
            {changed.has(entry.index) ? <circle cx={x} cy={-y} r="22" fill="none" stroke={SCENE_COLORS.changed} strokeWidth="2.5" /> : null}
            {resistant ? (
              <polygon points={`${x},${-y - 16} ${x + 16},${-y} ${x},${-y + 16} ${x - 16},${-y}`} fill={color} />
            ) : (
              <circle cx={x} cy={-y} r="15" fill={color} />
            )}
            <text x={x} y={-y + 5} textAnchor="middle" fontSize="13" fontWeight="700" fill="#0b1326">
              {resistant ? 'R' : 'S'}
            </text>
            <text x={x} y={-y + 32} textAnchor="middle" fontSize="11" fontWeight="700" fill="#fff">
              {entry.abbreviation ?? entry.displayName}
            </text>
            {selectedActionIndex === entry.index ? (
              <rect x={x + 14} y={-y - 24} width="8" height="16" rx="4" fill={SCENE_COLORS.capsuleCyan} />
            ) : null}
          </g>
        )
      })}
    </svg>
  )
}

import { useEffect, useId, useState } from 'react'
import { FiPause, FiPlay } from 'react-icons/fi'
import styles from './landing.module.css'
import edges from './network-edges.json'

const NODES = [
  { code: 'CIP', name: 'Ciprofloxacin', x: 190, y: 155, r: 27 },
  { code: 'NIT', name: 'Nitrofurantoin', x: 393, y: 96, r: 24 },
  { code: 'FOS', name: 'Fosfomycin', x: 524, y: 233, r: 34 },
  { code: 'TMP', name: 'Trimethoprim', x: 482, y: 420, r: 26 },
  { code: 'GEN', name: 'Gentamicin', x: 277, y: 488, r: 31 },
  { code: 'MEC', name: 'Mecillinam', x: 123, y: 351, r: 22 },
  { code: 'CAZ', name: 'Ceftazidime', x: 319, y: 281, r: 42 },
]
// Conceptual binary profiles for the public illustration; these are not policy outputs.
const PROFILES = ['0001000', '0101000', '0100000', '0000100']

export function ResistanceNetwork() {
  const id = useId().replaceAll(':', '')
  const [phase, setPhase] = useState(0)
  const [paused, setPaused] = useState(false)
  useEffect(() => {
    if (paused) return
    const media = window.matchMedia('(prefers-reduced-motion: reduce)')
    const timer = window.setInterval(() => {
      if (!media.matches && !document.hidden) setPhase((value) => (value + 1) % PROFILES.length)
    }, 3600)
    return () => window.clearInterval(timer)
  }, [paused])
  const profile = PROFILES[phase] ?? '0001000'
  return (
    <figure
      className={styles['network']}
      data-paused={paused}
      data-profile={profile}
      aria-label="Conceptual seven-antibiotic resistance network"
    >
      <div className={styles['networkHeading']}>
        <span>RESISTANCE EVOLUTION</span>
        <span className={styles['illustrative']}>Illustrative</span>
      </div>
      <svg
        className={styles['networkSvg']}
        viewBox="0 0 660 590"
        role="img"
        aria-label="Seven modeled antibiotics joined by documented interaction pairs. Colors cycle through conceptual susceptibility profiles; connections are shown without direction."
      >
        <defs>
          <radialGradient id={`${id}-blue`} cx="30%" cy="22%" r="85%">
            <stop stopColor="#e0f8ff" />
            <stop offset=".19" stopColor="#91d6ff" />
            <stop offset=".55" stopColor="#3979c5" />
            <stop offset="1" stopColor="#173668" />
          </radialGradient>
          <radialGradient id={`${id}-pink`} cx="30%" cy="22%" r="85%">
            <stop stopColor="#ffeaf6" />
            <stop offset=".2" stopColor="#e8b1e8" />
            <stop offset=".6" stopColor="#9b66bc" />
            <stop offset="1" stopColor="#4b386e" />
          </radialGradient>
          <radialGradient id={`${id}-aura`}>
            <stop stopColor="#6d9dfb" stopOpacity=".3" />
            <stop offset="1" stopColor="#548df7" stopOpacity="0" />
          </radialGradient>
          <filter id={`${id}-glow`} x="-100%" y="-100%" width="300%" height="300%">
            <feGaussianBlur stdDeviation="8" />
          </filter>
        </defs>
        <g className={styles['networkOrbit']}>
          <ellipse
            cx="327"
            cy="286"
            rx="245"
            ry="210"
            transform="rotate(-28 327 286)"
            fill="none"
            stroke="currentColor"
            strokeOpacity=".09"
          />
          <ellipse
            cx="327"
            cy="286"
            rx="267"
            ry="117"
            transform="rotate(48 327 286)"
            fill="none"
            stroke="currentColor"
            strokeOpacity=".07"
          />
          <circle cx="327" cy="286" r="240" fill={`url(#${id}-aura)`} />
          {edges.map((edge) => {
            const from = NODES[edge.from],
              to = NODES[edge.to]
            if (!from || !to) return null
            return (
              <line
                key={`${edge.from}-${edge.to}`}
                x1={from.x}
                y1={from.y}
                x2={to.x}
                y2={to.y}
                stroke="currentColor"
                strokeWidth={edge.from === 6 || edge.to === 6 ? 1.2 : 0.8}
                strokeOpacity={edge.from === 6 || edge.to === 6 ? 0.28 : 0.12}
              />
            )
          })}
          {NODES.map((node, index) => {
            const resistant = profile[index] === '1'
            return (
              <g key={node.code} className={styles['networkNode']}>
                <title>
                  {node.name}: {resistant ? 'resistant' : 'susceptible'} (illustrative)
                </title>
                <circle
                  cx={node.x}
                  cy={node.y}
                  r={node.r * 1.8}
                  fill={resistant ? '#be83e8' : '#69adff'}
                  opacity=".12"
                  filter={`url(#${id}-glow)`}
                />
                <circle
                  cx={node.x}
                  cy={node.y}
                  r={node.r + 6}
                  fill="none"
                  stroke={resistant ? '#d4a2e8' : '#92d5fa'}
                  strokeOpacity=".2"
                  strokeWidth=".8"
                />
                <circle
                  cx={node.x}
                  cy={node.y}
                  r={node.r}
                  fill={`url(#${id}-blue)`}
                  stroke="#a0d6fa"
                  strokeOpacity=".65"
                  strokeWidth=".7"
                />
                <circle
                  cx={node.x}
                  cy={node.y}
                  r={node.r}
                  fill={`url(#${id}-pink)`}
                  opacity={resistant ? 1 : 0}
                  stroke="#e0c0ee"
                  strokeOpacity=".65"
                  strokeWidth=".7"
                />
                <ellipse
                  cx={node.x - node.r * 0.22}
                  cy={node.y - node.r * 0.38}
                  rx={node.r * 0.38}
                  ry={node.r * 0.14}
                  fill="#e5f6ff"
                  opacity=".3"
                  transform={`rotate(-30 ${node.x} ${node.y})`}
                />
                <text
                  x={node.x + node.r + 11}
                  y={node.y + 4}
                  fill="currentColor"
                  fontSize="12"
                  letterSpacing="1.4"
                >
                  {node.code}
                </text>
              </g>
            )
          })}
        </g>
      </svg>
      <div className={styles['networkFooter']}>
        <span>
          <i />
          Susceptible
        </span>
        <span>
          <i className={styles['resistantDot']} />
          Resistant
        </span>
        <span className={styles['modeled']}>7 modeled antibiotics</span>
        <button
          type="button"
          aria-label={paused ? 'Play network animation' : 'Pause network animation'}
          aria-pressed={paused}
          onClick={() => setPaused((value) => !value)}
        >
          {paused ? <FiPlay /> : <FiPause />}
        </button>
      </div>
      <figcaption>
        Conceptual scientific visualization, not a representation of the simulation’s biological
        data.
      </figcaption>
    </figure>
  )
}

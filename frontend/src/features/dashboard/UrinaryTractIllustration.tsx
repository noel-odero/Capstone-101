/** A decorative picture of the urinary tract (kidneys, ureters, bladder) in a translucent torso. The data-driven 3D version is on the Simulation page. */
const KIDNEY_PATH =
  'M-2 -50 C24 -50 36 -34 34 -14 C33 -4 24 -2 24 8 C24 18 33 22 32 34 C30 48 14 54 -4 52 C-26 50 -38 26 -38 0 C-38 -28 -24 -50 -2 -50Z'

const LEFT_URETER = 'M96 92 C118 134 94 170 114 208 C122 228 140 240 142 254'
const RIGHT_URETER = 'M204 92 C182 134 206 170 186 208 C178 228 160 240 158 254'

const RIBS = [22, 44, 66]
const VERTEBRAE = Array.from({ length: 9 }, (_, index) => 8 + index * 21)

function Kidney({ transform, tint }: { transform: string; tint: 'cool' | 'warm' }) {
  return (
    <g transform={transform} filter="url(#ut-shadow)">
      <path d={KIDNEY_PATH} fill="url(#ut-kidney)" stroke="#cdbcff" strokeOpacity="0.55" strokeWidth="1.4" />
      <g clipPath="url(#ut-kidney-clip)">
        <ellipse cx="12" cy="26" rx="24" ry="30" fill={tint === 'warm' ? '#ef4444' : '#6d5ad9'} opacity={tint === 'warm' ? 0.7 : 0.35} filter="url(#ut-blur-lg)" />
        {tint === 'warm' ? <ellipse cx="22" cy="34" rx="12" ry="14" fill="#fb923c" opacity="0.6" filter="url(#ut-blur-md)" /> : null}
        <ellipse cx="-20" cy="-24" rx="9" ry="22" fill="#fff" opacity="0.38" filter="url(#ut-blur-sm)" transform="rotate(8 -20 -24)" />
        <path d="M-26 34 C-14 46 6 50 18 44" fill="none" stroke="#fff" strokeOpacity="0.22" strokeWidth="3" strokeLinecap="round" />
        <path d="M18 -26 C10 -10 10 12 18 28" fill="none" stroke="#2a1a63" strokeOpacity="0.28" strokeWidth="5" strokeLinecap="round" filter="url(#ut-blur-sm)" />
      </g>
      <path d="M26 -2 C34 -8 40 -14 46 -22" fill="none" stroke="#f59e0b" strokeWidth="3.4" strokeLinecap="round" />
      <path d="M26 14 C34 18 38 24 42 32" fill="none" stroke="#ef6a3a" strokeWidth="3" strokeLinecap="round" />
      <ellipse cx="25" cy="6" rx="7.5" ry="11" fill="url(#ut-pelvis)" />
      <ellipse cx="23" cy="2" rx="2.4" ry="4" fill="#fff" opacity="0.5" />
    </g>
  )
}

export function UrinaryTractIllustration({ className }: { className?: string | undefined }) {
  return (
    <svg className={className} viewBox="0 0 340 330" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Illustration of the urinary tract: two kidneys, two ureters and the bladder">
      <defs>
        <filter id="ut-blur-lg" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="9" />
        </filter>
        <filter id="ut-blur-md" x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="3.5" />
        </filter>
        <filter id="ut-blur-sm" x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="1.6" />
        </filter>
        <filter id="ut-shadow" x="-30%" y="-30%" width="170%" height="180%">
          <feDropShadow dx="0" dy="6" stdDeviation="5" floodColor="#3b2a86" floodOpacity="0.38" />
        </filter>

        <radialGradient id="ut-fade-gradient" cx="0.5" cy="0.5" r="0.62">
          <stop offset="0" stopColor="#fff" />
          <stop offset="0.55" stopColor="#fff" />
          <stop offset="1" stopColor="#000" />
        </radialGradient>
        <mask id="ut-fade" maskUnits="userSpaceOnUse" x="0" y="0" width="340" height="330">
          <rect width="340" height="330" fill="url(#ut-fade-gradient)" />
        </mask>

        <linearGradient id="ut-body" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#c3d7fa" stopOpacity="0.8" />
          <stop offset="1" stopColor="#dce8fd" stopOpacity="0.4" />
        </linearGradient>
        <radialGradient id="ut-kidney" cx="0.32" cy="0.28" r="0.85">
          <stop offset="0" stopColor="#9c82e6" />
          <stop offset="0.5" stopColor="#5d42b4" />
          <stop offset="1" stopColor="#33236f" />
        </radialGradient>
        <radialGradient id="ut-pelvis" cx="0.4" cy="0.35" r="0.8">
          <stop offset="0" stopColor="#fdba74" />
          <stop offset="1" stopColor="#ea580c" />
        </radialGradient>
        <clipPath id="ut-kidney-clip">
          <path d={KIDNEY_PATH} />
        </clipPath>

        <linearGradient id="ut-ureter-a" gradientUnits="userSpaceOnUse" x1="0" y1="90" x2="0" y2="254">
          <stop offset="0" stopColor="#fb923c" />
          <stop offset="0.45" stopColor="#fde047" />
          <stop offset="1" stopColor="#f59e0b" />
        </linearGradient>
        <linearGradient id="ut-ureter-b" gradientUnits="userSpaceOnUse" x1="0" y1="90" x2="0" y2="254">
          <stop offset="0" stopColor="#ef4444" />
          <stop offset="0.5" stopColor="#f97316" />
          <stop offset="1" stopColor="#fbbf24" />
        </linearGradient>
        <radialGradient id="ut-bladder" cx="0.5" cy="0.4" r="0.62">
          <stop offset="0" stopColor="#ef4444" />
          <stop offset="0.42" stopColor="#f6603a" />
          <stop offset="0.62" stopColor="#f9a03a" />
          <stop offset="0.8" stopColor="#fcd34d" />
          <stop offset="1" stopColor="#86efac" />
        </radialGradient>
        <linearGradient id="ut-urethra" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#bbf7d0" />
          <stop offset="1" stopColor="#22c55e" />
        </linearGradient>
      </defs>

      <g mask="url(#ut-fade)">
        <g transform="translate(20 0)">
          <g filter="url(#ut-blur-md)">
            <path
              d="M34 -10 C56 50 66 100 62 150 C58 190 30 240 14 340 L286 340 C270 240 242 190 238 150 C234 100 244 50 266 -10 Z"
              fill="url(#ut-body)"
            />
          </g>

          <g opacity="0.7" fill="#dbe7fb" stroke="#fff" strokeOpacity="0.6">
            {VERTEBRAE.map((y) => (
              <rect key={y} x="142" y={y} width="16" height="14" rx="5" />
            ))}
            <path d="M138 198 C142 232 148 246 150 252 C152 246 158 232 162 198 C154 204 146 204 138 198Z" />
            <path d="M66 206 C44 220 36 256 52 282 C68 268 86 246 98 226 C92 216 80 208 66 206Z" />
            <path d="M234 206 C256 220 264 256 248 282 C232 268 214 246 202 226 C208 216 220 208 234 206Z" />
          </g>
          <g fill="none" stroke="#fff" strokeOpacity="0.5" strokeWidth="3" strokeLinecap="round">
            {RIBS.map((y) => (
              <g key={y}>
                <path d={`M142 ${y} C112 ${y - 8} 86 ${y + 4} 66 ${y + 34}`} />
                <path d={`M158 ${y} C188 ${y - 8} 214 ${y + 4} 234 ${y + 34}`} />
              </g>
            ))}
          </g>
        </g>
      </g>

      <g transform="translate(20 0)">
        <Kidney transform="translate(72 84) rotate(-8) scale(0.92 1.18)" tint="cool" />
        <Kidney transform="translate(228 84) rotate(8) scale(-0.92 1.18)" tint="warm" />

        <g fill="none" strokeLinecap="round">
          <path d={LEFT_URETER} stroke="#6b5bd6" strokeOpacity="0.28" strokeWidth="11" filter="url(#ut-blur-sm)" />
          <path d={RIGHT_URETER} stroke="#6b5bd6" strokeOpacity="0.28" strokeWidth="11" filter="url(#ut-blur-sm)" />
          <path d={LEFT_URETER} stroke="url(#ut-ureter-a)" strokeWidth="6" />
          <path d={RIGHT_URETER} stroke="url(#ut-ureter-b)" strokeWidth="6" />
          <path d={LEFT_URETER} stroke="#fff" strokeOpacity="0.55" strokeWidth="1.4" transform="translate(-1.4 0)" />
          <path d={RIGHT_URETER} stroke="#fff" strokeOpacity="0.5" strokeWidth="1.4" transform="translate(-1.4 0)" />
        </g>

        <g transform="translate(150 272) scale(1.14) translate(-150 -272)">
          <ellipse cx="150" cy="274" rx="64" ry="52" fill="#ef4444" opacity="0.42" filter="url(#ut-blur-lg)" />
          <ellipse cx="150" cy="304" rx="48" ry="22" fill="#4ade80" opacity="0.5" filter="url(#ut-blur-lg)" />
          <path d="M143 304 L143 322 C143 331 157 331 157 322 L157 304Z" fill="url(#ut-urethra)" />
          <path d="M146 308 L146 322" stroke="#fff" strokeOpacity="0.55" strokeWidth="1.6" strokeLinecap="round" />
          <path
            d="M106 268 C104 244 126 232 150 232 C174 232 196 244 194 268 C192 294 172 310 150 310 C128 310 108 294 106 268Z"
            fill="url(#ut-bladder)"
            stroke="#fff"
            strokeOpacity="0.45"
            strokeWidth="1.2"
          />
          <ellipse cx="133" cy="253" rx="15" ry="8" fill="#fff" opacity="0.5" filter="url(#ut-blur-sm)" transform="rotate(-28 133 253)" />
          <circle cx="176" cy="288" r="3" fill="#fff" opacity="0.35" />
          <circle cx="142" cy="254" r="4.2" fill="#fb923c" />
          <circle cx="158" cy="254" r="4.2" fill="#f97316" />
        </g>
      </g>
    </svg>
  )
}

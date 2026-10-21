import { FiActivity, FiArrowUpRight, FiCheck, FiInfo } from 'react-icons/fi'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
} from 'recharts'
import type { ProfileRun } from './useProfileRun'
import { profilesFromSteps } from '@/domain/trajectory'
import { profileToCode } from '@/domain/profile'
import { ButtonLink } from '@/components/ui/Button'
import styles from './profile.module.css'

export function ProfileOverview({ run }: { run: ProfileRun }) {
  return (
    <>
      <section className={styles['overviewIdentity']} aria-label="Simulation profile summary">
        <span className={styles['overviewAvatar']}>
          <FiActivity size={30} />
        </span>
        <div>
          <h2>E. coli · {profileToCode(run.ppo.initialProfile)}</h2>
          <p>
            Simulated resistance profile <span>·</span> Seven antibiotics <span>·</span> Kigali,
            Rwanda
          </p>
        </div>
        <ButtonLink
          to={`/app/simulation/new?profile=${profileToCode(run.ppo.initialProfile)}`}
          variant="secondary"
          size="sm"
        >
          <FiArrowUpRight /> Edit profile
        </ButtonLink>
      </section>
    </>
  )
}

export function ProfileActivity({ run }: { run: ProfileRun }) {
  const points = profilesFromSteps(run.ppo.initialProfile, run.ppo.steps).map((profile, step) => ({
    step,
    resistant: profile.reduce<number>((sum, state) => sum + state, 0),
  }))
  return (
    <div className={styles['overviewGrid']}>
      <section className={styles['overviewCard']}>
        <h2>Resistance Trend</h2>
        <div style={{ height: 200, width: '100%' }}>
          <ResponsiveContainer>
            <LineChart data={points} margin={{ top: 20, right: 16, left: -25, bottom: 10 }}>
              <CartesianGrid vertical={false} stroke="var(--color-border)" />
              <XAxis
                dataKey="step"
                tick={{ fontSize: 11, fill: '#7289ad' }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                domain={[0, 7]}
                tick={{ fontSize: 11, fill: '#7289ad' }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip />
              <Line
                type="monotone"
                dataKey="resistant"
                name="Resistant antibiotics"
                stroke="#347cff"
                strokeWidth={2}
                dot={{ r: 3, fill: '#347cff' }}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <p className={styles['axisCaption']}>Step</p>
      </section>
      <section className={styles['overviewCard']}>
        <h2>Recent Activity</h2>
        <ol className={styles['activityList']}>
          <li>
            <FiCheck />
            <div>
              Step {run.ppo.steps.length}
              <p>PPO simulation completed</p>
            </div>
          </li>
          <li>
            <FiActivity />
            <div>
              Step 0<p>Simulation started · profile {profileToCode(run.ppo.initialProfile)}</p>
            </div>
          </li>
          <li>
            <FiInfo />
            <div>
              Model {run.provenance.algorithm}
              <p>Research simulation · {run.provenance.horizon} steps</p>
            </div>
          </li>
        </ol>
      </section>
    </div>
  )
}

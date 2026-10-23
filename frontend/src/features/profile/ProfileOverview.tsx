import { ButtonLink } from '@/components/ui/Button'
import { profileToCode } from '@/domain/profile'
import { buildTrajectorySeries } from '@/domain/metrics'
import { STRATEGY_COLORS, strategyLabel } from '@/domain/terminology'
import { FiActivity, FiArrowUpRight, FiCheck, FiInfo } from 'react-icons/fi'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import styles from './profile.module.css'
import type { ProfileRun } from './useProfileRun'

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
  const results = [run.ppo, ...(run.dqn ? [run.dqn] : []), ...(run.baseline ? [run.baseline] : [])]
  const points = buildTrajectorySeries(results, 'resistantCount')
  return (
    <div className={styles['overviewGrid']}>
      <section className={styles['overviewCard']}>
        <h2>Resistance Trend</h2>
        <div style={{ height: '12.5rem', width: '100%' }}>
          <ResponsiveContainer>
            <LineChart data={points} margin={{ top: 20, right: 16, left: -25, bottom: 10 }}>
              <CartesianGrid vertical={false} stroke="var(--color-border)" />
              <XAxis
                dataKey="step"
                tick={{ fontSize: '0.6875rem', fill: '#7289ad' }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                domain={[0, 7]}
                tick={{ fontSize: '0.6875rem', fill: '#7289ad' }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip />
              <Legend wrapperStyle={{ fontSize: '0.6875rem' }} />
              {results.map((result, index) => (
                <Line
                  key={result.strategy}
                  type="stepAfter"
                  dataKey={result.strategy}
                  name={strategyLabel(result.strategy)}
                  stroke={STRATEGY_COLORS[result.strategy]}
                  strokeWidth={2}
                  strokeDasharray={index === 0 ? undefined : index === 1 ? '3 3' : '6 3'}
                  dot={{ r: 3 }}
                  connectNulls={false}
                  isAnimationActive={false}
                />
              ))}
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
              <p>{results.map((result) => strategyLabel(result.strategy)).join(' · ')} completed</p>
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
              {run.dqn ? 'PPO + DQN' : run.provenance.algorithm}
              <p>Research simulation · {run.provenance.horizon} steps</p>
            </div>
          </li>
        </ol>
      </section>
    </div>
  )
}

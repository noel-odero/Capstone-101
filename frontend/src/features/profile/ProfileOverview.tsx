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
      <section className={styles['overviewIdentity']} aria-label="Analysis profile summary">
        <span className={styles['overviewAvatar']}>
          <FiActivity size={30} />
        </span>
        <div className={styles.identityCopy}>
          <h2>E. coli · {profileToCode(run.ppo.initialProfile)}</h2>
          <p>
            Initial resistance profile <span>·</span> Seven antibiotics <span>·</span> Model-based
            evaluation
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
      <section className={styles['overviewCard']} aria-labelledby="profile-trend-title">
        <h2 id="profile-trend-title">Resistance Trend</h2>
        <div className={styles.trendChart}>
          <ResponsiveContainer>
            <LineChart data={points} margin={{ top: 16, right: 12, left: 0, bottom: 10 }}>
              <CartesianGrid vertical={false} stroke="var(--color-border)" />
              <XAxis
                dataKey="step"
                tick={{ fontSize: '0.6875rem', fill: 'var(--color-text-muted)' }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                domain={[0, 7]}
                allowDecimals={false}
                width={32}
                tick={{ fontSize: '0.6875rem', fill: 'var(--color-text-muted)' }}
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
      <section className={styles['overviewCard']} aria-labelledby="profile-activity-title">
        <h2 id="profile-activity-title">Recent Activity</h2>
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
              Step 0<p>Analysis started · profile {profileToCode(run.ppo.initialProfile)}</p>
            </div>
          </li>
          <li>
            <FiInfo />
            <div>
              {run.dqn ? 'PPO + DQN' : run.provenance.algorithm}
              <p>Model-based evaluation · {run.provenance.horizon} steps</p>
            </div>
          </li>
        </ol>
      </section>
    </div>
  )
}

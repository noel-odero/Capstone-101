import type { CSSProperties } from 'react'
import { FiCheck } from 'react-icons/fi'
import { MODEL_STATES } from './model-states'
import styles from './model-explorer.module.css'

export function StateSpace({
  selected,
  filter,
  onSelect,
  onFilter,
}: {
  selected: string
  filter: number | null
  onSelect: (code: string) => void
  onFilter: (count: number | null) => void
}) {
  const groups = Array.from({ length: 8 }, (_, count) => ({
    count,
    states: MODEL_STATES.filter((state) => state.count === count),
  }))
  const visible = filter === null ? groups : groups.filter((group) => group.count === filter)
  return (
    <section className={styles.stateSpace} aria-labelledby="space-heading">
      <div className={styles.sectionHeading}>
        <div>
          <span className={styles.eyebrow}>01 / MODEL STRUCTURE</span>
          <h2 id="space-heading">Resistance state space</h2>
        </div>
        <span className={styles.total}>
          {filter === null ? 128 : visible[0]?.states.length} states
        </span>
      </div>
      <p className={styles.description}>Select a state to investigate its possible transitions.</p>
      <div
        className={styles.distribution}
        role="group"
        aria-label="Filter states by resistant count"
      >
        {groups.map((group) => (
          <button
            key={group.count}
            type="button"
            aria-label={`${group.count} resistant: ${group.states.length} states`}
            aria-pressed={filter === group.count}
            onClick={() => onFilter(filter === group.count ? null : group.count)}
            style={
              {
                '--count': group.count,
                '--bar-height': `${Math.max(4, (group.states.length / 35) * 55)}px`,
              } as CSSProperties
            }
          >
            <span className={styles.barValue}>{group.states.length}</span>
            <i />
            <span>{group.count}</span>
          </button>
        ))}
      </div>
      <div className={styles.filterCaption}>
        <span>{filter === null ? 'All resistant counts' : `${filter} resistant`}</span>
        <span>Number of resistant antibiotics</span>
        {filter !== null ? (
          <button type="button" onClick={() => onFilter(null)}>
            Show all
          </button>
        ) : null}
      </div>
      <div className={styles.stateGroups} data-filtered={filter !== null}>
        {visible.map((group) => (
          <div
            key={group.count}
            className={styles.stateGroup}
            style={{ '--count': group.count } as CSSProperties}
          >
            <div className={styles.groupLabel} aria-hidden="true">
              <strong>{group.count}</strong>
              <span>resistant</span>
            </div>
            <div
              className={styles.squares}
              role="group"
              aria-label={`${group.count} resistant states`}
            >
              {group.states.map((state) => (
                <button
                  key={state.code}
                  type="button"
                  aria-label={`State ${state.code}, ${state.count} resistant`}
                  aria-pressed={state.code === selected}
                  title={`${state.code} · ${state.count} resistant`}
                  onClick={() => onSelect(state.code)}
                >
                  {state.code === selected ? <FiCheck aria-hidden="true" /> : null}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
      <p className={styles.note}>
        Each square is a possible seven-bit profile. Colors show resistant counts—not prevalence,
        biological distance or transition probability.
      </p>
      <details className={styles.explainer}>
        <summary>Why 128 states?</summary>
        <p>
          Seven binary susceptibility flags give 2⁷ = 128 combinations. Group sizes are
          combinatorial, not measurements from 128 isolates. The all-resistant state has no eligible
          action. Policies also receive the previous action and step; this grid enumerates only the
          resistance component of their observation.
        </p>
      </details>
    </section>
  )
}

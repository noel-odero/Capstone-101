import { useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/Button'
import styles from './history.module.css'

export function HistoryFilters({
  params,
  onApply,
}: {
  params: URLSearchParams
  onApply: (values: Record<string, string>) => void
}) {
  const [error, setError] = useState('')
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const values = Object.fromEntries(new FormData(event.currentTarget)) as Record<string, string>
    if (values.from && values.to && values.from > values.to) {
      setError('The start date must precede the end date.')
      return
    }
    setError('')
    onApply(values)
  }
  return (
    <form className={styles.filters} onSubmit={submit} aria-label="Filter saved analyses">
      <label>
        Exact profile
        <input
          name="profile"
          defaultValue={params.get('profile') ?? ''}
          pattern="[01]{7}"
          maxLength={7}
          placeholder="e.g. 1000001"
          title="Seven digits, each 0 or 1"
        />
      </label>
      <label>
        Initially resistant
        <select
          name="initialResistantCount"
          defaultValue={params.get('initialResistantCount') ?? ''}
        >
          <option value="">Any count</option>
          {Array.from({ length: 8 }, (_, count) => (
            <option key={count} value={count}>
              {count} of 7
            </option>
          ))}
        </select>
      </label>
      <label>
        Strategy availability
        <select name="strategy" defaultValue={params.get('strategy') ?? ''}>
          <option value="">All analyses</option>
          <option value="ppo">PPO available</option>
          <option value="dqn">DQN available</option>
          <option value="baseline">Baseline available</option>
          <option value="missing_dqn">DQN unavailable</option>
        </select>
      </label>
      <label>
        Sort by
        <select name="sort" defaultValue={params.get('sort') ?? 'newest'}>
          <option value="newest">Newest first</option>
          <option value="oldest">Oldest first</option>
          <option value="ppo">PPO burden, lowest first</option>
          <option value="dqn">DQN burden, lowest first</option>
          <option value="baseline">Baseline burden, lowest first</option>
          <option value="disagreement">PPO / DQN difference, largest first</option>
        </select>
      </label>
      <label>
        From (UTC)
        <input type="date" name="from" defaultValue={params.get('from') ?? ''} />
      </label>
      <label>
        To (UTC)
        <input type="date" name="to" defaultValue={params.get('to') ?? ''} />
      </label>
      <Button type="submit" variant="secondary" size="sm">
        Apply filters
      </Button>
      <Button variant="ghost" size="sm" onClick={() => onApply({})}>
        Clear filters
      </Button>
      {error ? <p role="alert">{error}</p> : null}
    </form>
  )
}

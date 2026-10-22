import { ApiError } from '@/api/api-errors'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Button } from './Button'
import { EmptyState } from './EmptyState'
import { ErrorState } from './ErrorState'
import { LoadingState } from './LoadingState'
import { StatusIndicator } from './StatusIndicator'
import { Tooltip } from './Tooltip'

describe('LoadingState', () => {
  it('announces progress politely without showing a percentage', () => {
    render(<LoadingState label="Loading recent runs" />)
    const status = screen.getByRole('status')
    expect(status).toHaveTextContent('Loading recent runs')
    expect(status).toHaveAttribute('aria-live', 'polite')
    expect(status.textContent).not.toMatch(/%/)
  })
})

describe('EmptyState', () => {
  it('explains the absence and offers the next action', () => {
    render(
      <EmptyState
        title="No runs yet"
        description="Run a comparison first."
        action={<button type="button">Start</button>}
      />,
    )
    expect(screen.getByRole('heading', { name: 'No runs yet' })).toBeInTheDocument()
    expect(screen.getByText('Run a comparison first.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Start' })).toBeInTheDocument()
  })
})

describe('ErrorState', () => {
  it('shows the message, code and correlation id as an alert, without a stack trace', () => {
    const error = new ApiError({
      kind: 'dependency_unavailable',
      message: 'The database is unavailable.',
      code: 'database_unavailable',
      correlationId: 'abc123',
    })
    render(<ErrorState error={error} />)
    const alert = screen.getByRole('alert')
    expect(within(alert).getByText('The database is unavailable.')).toBeInTheDocument()
    expect(within(alert).getByText(/Error code: database_unavailable/)).toBeInTheDocument()
    expect(within(alert).getByText(/Correlation ID: abc123/)).toBeInTheDocument()
    expect(alert.textContent).not.toMatch(/\bat \w+\.\w+|stack/i)
  })

  it('lists field errors for a validation failure', () => {
    const error = new ApiError({
      kind: 'validation',
      message: 'Not valid.',
      fieldErrors: { resistanceProfile: ['Must have 7 values.'] },
    })
    render(<ErrorState error={error} />)
    expect(screen.getByText(/Must have 7 values\./)).toBeInTheDocument()
  })

  it('offers retry only when the caller says retrying is safe', async () => {
    const onRetry = vi.fn()
    const { rerender } = render(
      <ErrorState error={new ApiError({ kind: 'network', message: 'x' })} />,
    )
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()

    rerender(
      <ErrorState error={new ApiError({ kind: 'network', message: 'x' })} onRetry={onRetry} />,
    )
    await userEvent.setup().click(screen.getByRole('button', { name: 'Try again' }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })
})

describe('Tooltip', () => {
  it('opens on focus and closes with Escape', async () => {
    const user = userEvent.setup()
    render(<Tooltip label="What is susceptible?">A simulator flag.</Tooltip>)
    await user.tab()
    expect(screen.getByRole('tooltip')).toBeInTheDocument()
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  })
})

describe('StatusIndicator', () => {
  it.each([
    ['susceptible', 'Susceptible'],
    ['resistant', 'Resistant'],
    ['unsupported', 'No supported transition data'],
    ['supported', 'Transition data available'],
    ['warning', 'No feasible actions remain'],
  ] as const)('writes the %s status in words, not colour alone', (kind, label) => {
    render(<StatusIndicator kind={kind} label={label} />)
    expect(screen.getByText(label)).toBeVisible()
  })
})

describe('Button', () => {
  it('blocks activation while loading', async () => {
    const onClick = vi.fn()
    render(
      <Button loading onClick={onClick}>
        Run
      </Button>,
    )
    const button = screen.getByRole('button', { name: 'Run' })
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('aria-busy', 'true')
    await userEvent.setup().click(button)
    expect(onClick).not.toHaveBeenCalled()
  })
})

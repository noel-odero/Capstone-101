import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { setCsrfToken } from '@/api/http-client'
import { baseRoutes, mockFetch, type MockRoutes } from '@/test/mock-api'
import { renderApp } from '@/test/test-utils'

const anonymous = { isAuthenticated: false, user: null, csrfToken: 'anonymous-token' }
const signedIn = {
  isAuthenticated: true,
  user: { displayName: 'Ada Researcher', email: 'ada@example.org' },
  csrfToken: 'user-token',
}

const pendingVerification = () => ({
  verificationRequired: true,
  challengeToken: 'a'.repeat(43),
  email: 'ada@example.org',
  expiresAtUtc: new Date(Date.now() + 600_000).toISOString(),
  resendAvailableAtUtc: new Date(Date.now() + 60_000).toISOString(),
})

const problem = (status: number, code: string, detail: string, extra: object = {}) => ({
  status,
  body: { status, code, detail, ...extra },
})

function routesFor(session: unknown, overrides: MockRoutes = {}): MockRoutes {
  return baseRoutes({ 'GET /api/v1/auth/session': { body: session }, ...overrides })
}

async function fillAndSubmit(
  user: ReturnType<typeof userEvent.setup>,
  {
    email,
    password,
    name,
    button,
  }: { email?: string; password?: string; name?: string; button: string },
) {
  if (name !== undefined) {
    await user.type(await screen.findByLabelText(/^Name/), name)
  }
  if (email !== undefined) {
    await user.type(await screen.findByLabelText('Email'), email)
  }
  if (password !== undefined) {
    await user.type(screen.getByLabelText('Password', { selector: 'input' }), password)
  }
  await user.click(screen.getByRole('button', { name: button }))
}

describe('email and password authentication', () => {
  beforeEach(() => {
    setCsrfToken(null)
    sessionStorage.removeItem('stewardlab.email-verification')
  })
  afterEach(() => {
    setCsrfToken(null)
    sessionStorage.removeItem('stewardlab.email-verification')
  })

  it('sends a signed-out visitor from the workspace to sign-in and remembers where they were going', async () => {
    mockFetch(routesFor(anonymous))
    const { router } = renderApp('/app/simulation')

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/auth/sign-in')
    expect(router.state.location.search).toBe('?returnTo=%2Fapp%2Fsimulation')
  })

  it('signs in, sends the anonymous CSRF token with the credentials, and lands where the visitor was going', async () => {
    const api = mockFetch(routesFor(anonymous, { 'POST /api/v1/auth/sign-in': { body: signedIn } }))
    const user = userEvent.setup()
    const { router } = renderApp('/auth/sign-in?returnTo=%2Fapp%2Fprofile')

    await fillAndSubmit(user, {
      email: ' ada@example.org ',
      password: 'a long enough password',
      button: 'Sign in',
    })

    await waitFor(() => expect(router.state.location.pathname).toBe('/app/profile'))
    const call = api.callsTo('POST /api/v1/auth/sign-in')
    expect(call).toHaveLength(1)
    expect(call[0]?.body).toEqual({ email: 'ada@example.org', password: 'a long enough password' })
    const init = api.fetchMock.mock.calls.find(
      ([input, options]) => String(input).endsWith('/auth/sign-in') && options?.method === 'POST',
    )?.[1]
    expect((init?.headers as Record<string, string>)['X-CSRF-TOKEN']).toBe('anonymous-token')
  })

  it('uses the token returned at sign-in for the next state-changing request', async () => {
    const api = mockFetch(
      routesFor(anonymous, {
        'POST /api/v1/auth/sign-in': { body: signedIn },
        'POST /api/v1/auth/sign-out': { status: 204 },
      }),
    )
    const user = userEvent.setup()
    renderApp('/auth/sign-in')
    await fillAndSubmit(user, {
      email: 'ada@example.org',
      password: 'a long enough password',
      button: 'Sign in',
    })
    await user.click(await screen.findByRole('button', { name: 'Sign out' }))

    await waitFor(() => expect(api.callsTo('POST /api/v1/auth/sign-out')).toHaveLength(1))
    const init = api.fetchMock.mock.calls.find(
      ([input, options]) => String(input).endsWith('/auth/sign-out') && options?.method === 'POST',
    )?.[1]
    expect((init?.headers as Record<string, string>)['X-CSRF-TOKEN']).toBe('user-token')
  })

  it('shows the server message for a wrong password, stays on the page, and keeps what was typed', async () => {
    mockFetch(
      routesFor(anonymous, {
        'POST /api/v1/auth/sign-in': problem(
          401,
          'invalid_credentials',
          'The email or password is incorrect.',
        ),
      }),
    )
    const user = userEvent.setup()
    const { router } = renderApp('/auth/sign-in')

    await fillAndSubmit(user, {
      email: 'ada@example.org',
      password: 'wrong password',
      button: 'Sign in',
    })

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The email or password is incorrect.',
    )
    expect(router.state.location.pathname).toBe('/auth/sign-in')
    expect(screen.getByLabelText('Email')).toHaveValue('ada@example.org')
  })

  it('tells a locked-out user to wait, using the server message', async () => {
    mockFetch(
      routesFor(anonymous, {
        'POST /api/v1/auth/sign-in': problem(
          429,
          'too_many_attempts',
          'Too many failed attempts. Try again in 15 minutes.',
        ),
      }),
    )
    const user = userEvent.setup()
    renderApp('/auth/sign-in')

    await fillAndSubmit(user, {
      email: 'ada@example.org',
      password: 'a long enough password',
      button: 'Sign in',
    })

    expect(await screen.findByRole('alert')).toHaveTextContent('Try again in 15 minutes.')
  })

  it('does not call the server when sign-in fields are empty and puts focus on the first problem', async () => {
    const api = mockFetch(routesFor(anonymous))
    const user = userEvent.setup()
    renderApp('/auth/sign-in')

    await user.click(await screen.findByRole('button', { name: 'Sign in' }))

    expect(await screen.findByText('Enter your email address.')).toBeInTheDocument()
    expect(screen.getByText('Enter your password.')).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toHaveFocus()
    expect(screen.getByLabelText('Email')).toHaveAttribute('aria-invalid', 'true')
    expect(api.callsTo('POST /api/v1/auth/sign-in')).toHaveLength(0)
  })

  it('keeps registration outside the workspace until the email code is verified', async () => {
    const api = mockFetch(
      routesFor(anonymous, {
        'POST /api/v1/auth/register': { status: 202, body: pendingVerification() },
        'POST /api/v1/auth/verify-email': { body: signedIn },
      }),
    )
    const user = userEvent.setup()
    const { router } = renderApp('/auth/register')

    await fillAndSubmit(user, {
      name: 'Ada Researcher',
      email: 'ada.researcher+amr@gmail.com',
      password: 'a long enough password',
      button: 'Create account',
    })

    expect(await screen.findByRole('heading', { name: 'Verify your email' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/auth/register')
    expect(screen.getByRole('button', { name: /Resend in/ })).toBeDisabled()
    await user.type(screen.getByLabelText('Verification code'), '012345')
    await user.click(screen.getByRole('button', { name: 'Verify email' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/app'))
    expect(api.callsTo('POST /api/v1/auth/verify-email')[0]?.body).toEqual({
      challengeToken: 'a'.repeat(43),
      code: '012345',
    })
    expect(sessionStorage.getItem('stewardlab.email-verification')).toBeNull()
    expect(api.callsTo('POST /api/v1/auth/register')[0]?.body).toEqual({
      email: 'ada.researcher+amr@gmail.com',
      password: 'a long enough password',
      displayName: 'Ada Researcher',
    })
    expect(await screen.findByRole('heading', { name: /Research.*Workspace/ })).toBeInTheDocument()
  })

  it('omits the name when it is left blank', async () => {
    const api = mockFetch(
      routesFor(anonymous, {
        'POST /api/v1/auth/register': { status: 202, body: pendingVerification() },
      }),
    )
    const user = userEvent.setup()
    renderApp('/auth/register')

    await fillAndSubmit(user, {
      email: 'ada@example.org',
      password: 'a long enough password',
      button: 'Create account',
    })

    await waitFor(() => expect(api.callsTo('POST /api/v1/auth/register')).toHaveLength(1))
    expect(api.callsTo('POST /api/v1/auth/register')[0]?.body).toEqual({
      email: 'ada@example.org',
      password: 'a long enough password',
    })
  })

  it('checks the new password and the email before sending anything', async () => {
    const api = mockFetch(routesFor(anonymous))
    const user = userEvent.setup()
    renderApp('/auth/register')

    await fillAndSubmit(user, {
      email: 'not-an-email',
      password: 'short',
      button: 'Create account',
    })

    expect(await screen.findByText(/Enter a valid email address/)).toBeInTheDocument()
    expect(screen.getByText('Use at least 10 characters.')).toBeInTheDocument()
    expect(api.callsTo('POST /api/v1/auth/register')).toHaveLength(0)
  })

  it('offers sign-in from pending registration without revealing whether an email already exists', async () => {
    mockFetch(
      routesFor(anonymous, {
        'POST /api/v1/auth/register': { status: 202, body: pendingVerification() },
      }),
    )
    const user = userEvent.setup()
    renderApp('/auth/register')

    await fillAndSubmit(user, {
      email: 'ada@example.org',
      password: 'a long enough password',
      button: 'Create account',
    })

    expect(await screen.findByRole('heading', { name: 'Verify your email' })).toBeInTheDocument()
    expect(screen.getByText('Already have an account?')).toBeInTheDocument()
    await user.click(within(screen.getByRole('main')).getByRole('link', { name: 'Sign in' }))
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(sessionStorage.getItem('stewardlab.email-verification')).toBeNull()
  })

  it('shows code errors and lets an existing account complete verification after signing in', async () => {
    mockFetch(
      routesFor(anonymous, {
        'POST /api/v1/auth/sign-in': { status: 202, body: pendingVerification() },
        'POST /api/v1/auth/verify-email': problem(
          422,
          'invalid_verification_code',
          'Invalid code.',
        ),
      }),
    )
    const user = userEvent.setup()
    const { router } = renderApp('/auth/sign-in')
    await fillAndSubmit(user, {
      email: 'ada@example.org',
      password: 'a long enough password',
      button: 'Sign in',
    })
    expect(await screen.findByRole('heading', { name: 'Verify your email' })).toBeInTheDocument()
    await user.type(screen.getByLabelText('Verification code'), '111111')
    await user.click(screen.getByRole('button', { name: 'Verify email' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The code is incorrect or no longer valid.',
    )
    expect(router.state.location.pathname).toBe('/auth/sign-in')
  })

  it('restores a pending verification on reload and replaces the ticket when resending', async () => {
    sessionStorage.setItem(
      'stewardlab.email-verification',
      JSON.stringify({
        ...pendingVerification(),
        resendAvailableAtUtc: new Date(Date.now() - 1000).toISOString(),
      }),
    )
    const api = mockFetch(
      routesFor(anonymous, {
        'POST /api/v1/auth/resend-verification': {
          status: 202,
          body: { ...pendingVerification(), challengeToken: 'b'.repeat(43) },
        },
      }),
    )
    const user = userEvent.setup()
    renderApp('/auth/register')
    expect(await screen.findByRole('heading', { name: 'Verify your email' })).toBeInTheDocument()
    await user.click(await screen.findByRole('button', { name: 'Resend code' }))
    expect(await screen.findByRole('status')).toHaveTextContent('A new code has been sent.')
    expect(api.callsTo('POST /api/v1/auth/resend-verification')[0]?.body).toEqual({
      challengeToken: 'a'.repeat(43),
    })
    expect(
      JSON.parse(sessionStorage.getItem('stewardlab.email-verification') ?? '{}').challengeToken,
    ).toBe('b'.repeat(43))
  })

  it('maps field errors from a server validation response onto the fields', async () => {
    mockFetch(
      routesFor(anonymous, {
        'POST /api/v1/auth/register': problem(422, 'validation_failed', 'x', {
          errors: { password: ['Use a password of 10 to 128 characters.'] },
        }),
      }),
    )
    const user = userEvent.setup()
    renderApp('/auth/register')

    await fillAndSubmit(user, {
      email: 'ada@example.org',
      password: 'a long enough password',
      button: 'Create account',
    })

    expect(await screen.findByText('Use a password of 10 to 128 characters.')).toBeInTheDocument()
    expect(screen.getByLabelText('Password', { selector: 'input' })).toHaveFocus()
  })

  it('submits once however many times the button is pressed, and never retries by itself', async () => {
    const api = mockFetch(routesFor(anonymous))
    const respond = api.fetchMock.getMockImplementation()
    if (!respond) {
      throw new Error('The mock has no implementation to delegate to.')
    }
    let release: () => void = () => undefined
    api.fetchMock.mockImplementation(async (input, init) => {
      if (String(input).endsWith('/auth/sign-in')) {
        await new Promise<void>((resolve) => {
          release = resolve
        })
        return new Response(JSON.stringify(signedIn))
      }
      return respond(input, init)
    })
    const signInCalls = () =>
      api.fetchMock.mock.calls.filter(([input]) => String(input).endsWith('/auth/sign-in'))
    const user = userEvent.setup()
    renderApp('/auth/sign-in')

    await user.type(await screen.findByLabelText('Email'), 'ada@example.org')
    await user.type(
      screen.getByLabelText('Password', { selector: 'input' }),
      'a long enough password',
    )
    const button = screen.getByRole('button', { name: 'Sign in' })
    await user.click(button)
    await user.click(button)
    await user.keyboard('{Enter}')

    expect(button).toBeDisabled()
    expect(signInCalls()).toHaveLength(1)
    release()
    expect(await screen.findByRole('heading', { name: /Research.*Workspace/ })).toBeInTheDocument()
    expect(signInCalls()).toHaveLength(1)
  })

  it('shows and hides the password on request', async () => {
    mockFetch(routesFor(anonymous))
    const user = userEvent.setup()
    renderApp('/auth/sign-in')

    const field = await screen.findByLabelText('Password', { selector: 'input' })
    expect(field).toHaveAttribute('type', 'password')
    await user.click(screen.getByRole('button', { name: 'Show password' }))
    expect(field).toHaveAttribute('type', 'text')
    expect(screen.getByRole('button', { name: 'Hide password' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('offers the right browser hints for password managers', async () => {
    mockFetch(routesFor(anonymous))
    renderApp('/auth/register')

    expect(await screen.findByLabelText('Email')).toHaveAttribute('autocomplete', 'email')
    expect(screen.getByLabelText('Password', { selector: 'input' })).toHaveAttribute(
      'autocomplete',
      'new-password',
    )
  })

  it('sends someone who is already signed in straight past the sign-in and register pages', async () => {
    mockFetch(routesFor(signedIn))
    const { router } = renderApp('/auth/register?returnTo=%2Fapp%2Fhistory')

    await waitFor(() => expect(router.state.location.pathname).toBe('/app/history'))
  })

  it('refuses an open redirect in returnTo', async () => {
    mockFetch(routesFor(signedIn))
    const { router } = renderApp('/auth/sign-in?returnTo=https%3A%2F%2Fevil.example%2F')

    await waitFor(() => expect(router.state.location.pathname).toBe('/app'))
  })

  it('signs out, returns to the landing page, and forgets the user', async () => {
    let session: unknown = signedIn
    mockFetch(
      baseRoutes({
        'GET /api/v1/auth/session': () => ({ body: session }),
        'POST /api/v1/auth/sign-out': () => {
          session = anonymous
          return { status: 204 }
        },
      }),
    )
    const user = userEvent.setup()
    const { router } = renderApp('/app')

    await user.click(await screen.findByRole('button', { name: 'Sign out' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/'))
    expect(screen.queryByText('Ada Researcher')).not.toBeInTheDocument()
    await waitFor(() =>
      expect(
        within(screen.getByRole('banner')).getByRole('link', { name: 'Sign in' }),
      ).toBeInTheDocument(),
    )
    await router.navigate('/app')
    await waitFor(() => expect(router.state.location.pathname).toBe('/'))
  })

  it('treats a 401 from a protected call as an ended session and returns to sign-in with a notice', async () => {
    mockFetch(
      baseRoutes({
        'GET /api/v1/auth/session': { body: signedIn },
        'GET /api/v1/simulations/recent': problem(
          401,
          'authentication_required',
          'Sign in to continue.',
        ),
      }),
    )
    const { router } = renderApp('/app/history')

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/auth/sign-in')
    expect(within(screen.getByRole('main')).getByRole('status')).toHaveTextContent(
      'Your session ended',
    )
  })

  it('says the server cannot be reached, with a retry, when the session check fails', async () => {
    mockFetch(baseRoutes({ 'GET /api/v1/auth/session': { networkError: true } }))
    renderApp('/auth/sign-in')

    expect(await screen.findByText('The server could not be reached.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })
})

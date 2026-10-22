export type AccountMode = 'sign-in' | 'register'

export type AccountField = 'email' | 'password' | 'displayName'
export type AccountErrors = Partial<Record<AccountField, string>>

export const MIN_PASSWORD_LENGTH = 10
export const MAX_PASSWORD_LENGTH = 128
export const MAX_NAME_LENGTH = 80

/** The same shape the server accepts, so most mistakes are caught before a request is sent. */
const EMAIL_PATTERN =
  /^(?!\.)(?!.*\.\.)[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}(?<!\.)@(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z0-9-]{2,63}$/

export interface AccountValues {
  email: string
  password: string
  displayName?: string
}

export function validateAccount(mode: AccountMode, values: AccountValues): AccountErrors {
  const errors: AccountErrors = {}
  const email = values.email.trim()

  if (email === '') {
    errors.email = 'Enter your email address.'
  } else if (mode === 'register' && (email.length > 254 || !EMAIL_PATTERN.test(email))) {
    errors.email = 'Enter a valid email address, such as name@example.org.'
  }

  if (values.password === '') {
    errors.password = mode === 'register' ? 'Choose a password.' : 'Enter your password.'
  } else if (mode === 'register' && values.password.length < MIN_PASSWORD_LENGTH) {
    errors.password = `Use at least ${MIN_PASSWORD_LENGTH} characters.`
  } else if (values.password.length > MAX_PASSWORD_LENGTH) {
    errors.password = `Use at most ${MAX_PASSWORD_LENGTH} characters.`
  }

  if (mode === 'register' && (values.displayName?.trim().length ?? 0) > MAX_NAME_LENGTH) {
    errors.displayName = `Use at most ${MAX_NAME_LENGTH} characters.`
  }

  return errors
}

export function firstInvalidField(errors: AccountErrors): AccountField | undefined {
  return (['email', 'password', 'displayName'] as const).find(
    (field) => errors[field] !== undefined,
  )
}

/** Keeps only the fields the form has, from the server's `{ field: [messages] }` map. */
export function fromServerFieldErrors(
  fieldErrors: Readonly<Record<string, readonly string[]>>,
): AccountErrors {
  const errors: AccountErrors = {}
  for (const field of ['email', 'password', 'displayName'] as const) {
    const message = fieldErrors[field]?.[0]
    if (message) {
      errors[field] = message
    }
  }
  return errors
}

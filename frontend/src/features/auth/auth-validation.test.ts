import { describe, expect, it } from 'vitest'
import { safeReturnTo } from './auth-api'
import { firstInvalidField, fromServerFieldErrors, validateAccount } from './auth-validation'

describe('validateAccount', () => {
  const valid = { email: 'anoel.odero@gmail.com', password: 'a long enough password' }

  it('accepts ordinary real-world email addresses when registering', () => {
    for (const email of [
      'anoel.odero@gmail.com',
      'first.last+tag@sub.example.co.uk',
      "o'brien@example.ie",
      'user_name-1@my-domain.org',
      'A@b.io',
    ]) {
      expect(validateAccount('register', { ...valid, email }), email).toEqual({})
    }
  })

  it('rejects malformed addresses when registering', () => {
    for (const email of [
      'plainaddress',
      '@example.org',
      'name@',
      'name@example',
      'name@example.c',
      '.name@example.org',
      'na..me@example.org',
      'na me@example.org',
      'name@@example.org',
    ]) {
      expect(validateAccount('register', { ...valid, email }).email, email).toMatch(/valid email/i)
    }
  })

  it('trims the email before checking it', () => {
    expect(validateAccount('register', { ...valid, email: '  anoel.odero@gmail.com  ' })).toEqual(
      {},
    )
  })

  it('asks for the email and password when they are empty, in both modes', () => {
    expect(validateAccount('sign-in', { email: '', password: '' })).toEqual({
      email: 'Enter your email address.',
      password: 'Enter your password.',
    })
    expect(validateAccount('register', { email: ' ', password: '' })).toEqual({
      email: 'Enter your email address.',
      password: 'Choose a password.',
    })
  })

  it('requires at least 10 characters for a new password but lets an existing one be tried at sign-in', () => {
    expect(validateAccount('register', { ...valid, password: 'short' }).password).toBe(
      'Use at least 10 characters.',
    )
    expect(validateAccount('register', { ...valid, password: '1234567890' })).toEqual({})
    expect(validateAccount('sign-in', { email: 'a@b.io', password: 'short' })).toEqual({})
  })

  it('does not reject a sign-in email for its shape, so a typo is answered by the server like any wrong login', () => {
    expect(validateAccount('sign-in', { email: 'not-an-email', password: 'x' })).toEqual({})
  })

  it('limits the password and name lengths', () => {
    expect(validateAccount('register', { ...valid, password: 'a'.repeat(129) }).password).toBe(
      'Use at most 128 characters.',
    )
    expect(validateAccount('register', { ...valid, displayName: 'n'.repeat(81) }).displayName).toBe(
      'Use at most 80 characters.',
    )
  })

  it('reports the first invalid field in form order', () => {
    expect(firstInvalidField({ password: 'x', email: 'y' })).toBe('email')
    expect(firstInvalidField({ displayName: 'z', password: 'x' })).toBe('password')
    expect(firstInvalidField({})).toBeUndefined()
  })

  it('keeps only the form fields from a server validation response', () => {
    expect(
      fromServerFieldErrors({
        email: ['Enter a valid email address.', 'ignored'],
        unknown: ['x'],
        displayName: [],
      }),
    ).toEqual({ email: 'Enter a valid email address.' })
  })
})

describe('safeReturnTo', () => {
  it('keeps workspace paths and refuses anything else', () => {
    expect(safeReturnTo('/app/simulation?profile=0100000')).toBe('/app/simulation?profile=0100000')
    expect(safeReturnTo('/app')).toBe('/app')
    for (const value of [
      null,
      undefined,
      '',
      'app',
      '//evil.example',
      'https://evil.example/app',
      '/\\evil',
      '/about',
      '/api/v1/auth/session',
      `/app/${'a'.repeat(400)}`,
    ]) {
      expect(safeReturnTo(value), String(value)).toBe('/app')
    }
  })
})

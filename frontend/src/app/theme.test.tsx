import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ThemeControl } from '@/components/ui/ThemeControl'
import { initializeTheme, readThemePreference, setThemePreference, THEME_KEY } from './theme'

let dispose: () => void
let systemChanged: ((event: MediaQueryListEvent) => void) | undefined
let systemDark = false

beforeEach(() => {
  localStorage.clear()
  systemDark = false
  vi.spyOn(window, 'matchMedia').mockImplementation(
    () =>
      ({
        get matches() {
          return systemDark
        },
        addEventListener: (_: string, callback: EventListenerOrEventListenerObject) => {
          systemChanged = callback as (event: MediaQueryListEvent) => void
        },
        removeEventListener: vi.fn(),
      }) as unknown as MediaQueryList,
  )
  dispose = initializeTheme()
})

afterEach(() => {
  dispose()
  localStorage.clear()
  vi.restoreAllMocks()
  document.documentElement.removeAttribute('data-theme')
})

describe('Appearance preference', () => {
  it('persists a selected theme and restores it at initialization', async () => {
    render(<ThemeControl />)
    await userEvent.setup().click(screen.getByRole('radio', { name: 'Dark theme' }))
    expect(document.documentElement).toHaveAttribute('data-theme', 'dark')
    expect(localStorage.getItem(THEME_KEY)).toBe('dark')
    dispose()
    dispose = initializeTheme()
    expect(document.documentElement).toHaveAttribute('data-theme', 'dark')
  })

  it('follows system changes only when System is selected', () => {
    act(() => {
      systemDark = true
      systemChanged?.({ matches: true } as MediaQueryListEvent)
    })
    expect(document.documentElement).toHaveAttribute('data-theme', 'dark')
    act(() => setThemePreference('light'))
    act(() => systemChanged?.({ matches: true } as MediaQueryListEvent))
    expect(document.documentElement).toHaveAttribute('data-theme', 'light')
  })

  it('updates mounted controls when the preference changes in another tab', () => {
    render(<ThemeControl />)
    act(() => {
      localStorage.setItem(THEME_KEY, 'dark')
      window.dispatchEvent(new StorageEvent('storage', { key: THEME_KEY, newValue: 'dark' }))
    })
    expect(screen.getByRole('radio', { name: 'Dark theme' })).toHaveAttribute(
      'aria-checked',
      'true',
    )
    expect(document.documentElement).toHaveAttribute('data-theme', 'dark')
  })

  it('still switches theme when storage is unavailable', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    expect(() => setThemePreference('dark')).not.toThrow()
    expect(document.documentElement).toHaveAttribute('data-theme', 'dark')
  })

  it('uses System for corrupt stored values or inaccessible storage', () => {
    localStorage.setItem(THEME_KEY, 'invalid')
    expect(readThemePreference()).toBe('system')
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    expect(readThemePreference()).toBe('system')
  })
})

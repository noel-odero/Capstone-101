import { useSyncExternalStore } from 'react'

export type ThemePreference = 'light' | 'dark' | 'system'
export const THEME_KEY = 'amr.theme'

export function readThemePreference(): ThemePreference {
  try {
    const value = localStorage.getItem(THEME_KEY)
    return value === 'light' || value === 'dark' ? value : 'system'
  } catch {
    return 'system'
  }
}

let preference = readThemePreference()
const listeners = new Set<() => void>()

function applyTheme() {
  const dark =
    preference === 'dark' ||
    (preference === 'system' && window.matchMedia?.('(prefers-color-scheme: dark)').matches)
  document.documentElement.dataset['theme'] = dark ? 'dark' : 'light'
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute('content', dark ? '#232325' : '#f5f5f3')
}

export function setThemePreference(value: ThemePreference) {
  preference = value
  try {
    localStorage.setItem(THEME_KEY, value)
  } catch {
    // The theme still works for this visit when browser storage is unavailable.
  }
  applyTheme()
  listeners.forEach((listener) => listener())
}

/** Also follows operating-system changes and preferences changed in another tab. */
export function initializeTheme() {
  preference = readThemePreference()
  applyTheme()
  const media = window.matchMedia?.('(prefers-color-scheme: dark)')
  const onSystemChange = () => applyTheme()
  const onStorage = (event: StorageEvent) => {
    if (event.key === THEME_KEY || event.key === null) {
      preference = readThemePreference()
      applyTheme()
      listeners.forEach((listener) => listener())
    }
  }
  media?.addEventListener('change', onSystemChange)
  window.addEventListener('storage', onStorage)
  return () => {
    media?.removeEventListener('change', onSystemChange)
    window.removeEventListener('storage', onStorage)
  }
}

export function useThemePreference() {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    () => preference,
    () => 'system' as ThemePreference,
  )
}

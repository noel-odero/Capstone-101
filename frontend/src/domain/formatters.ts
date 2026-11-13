import { UNAVAILABLE } from './metrics'

export function formatDateTime(iso: string, locale?: string, timeZone?: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) {
    return UNAVAILABLE
  }
  return new Intl.DateTimeFormat(locale, {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone,
  }).format(date)
}

import { UNAVAILABLE } from './metrics'

const SHORT_ID_LENGTH = 8

export function shortId(id: string): string {
  return id.slice(0, SHORT_ID_LENGTH)
}

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

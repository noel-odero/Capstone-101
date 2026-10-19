/** Seed range accepted by the API (unsigned 32-bit), as documented in the backend contract. */
export const SEED_MIN = 0
export const SEED_MAX = 4_294_967_295

export type SeedParseResult =
  | { ok: true; value: number | undefined }
  | { ok: false; message: string }

/**
 * Parses an optional seed field. Empty input is valid and means "let the service generate one"; anything else must be
 * a whole number within the accepted range.
 */
export function parseSeedInput(text: string): SeedParseResult {
  const trimmed = text.trim()
  if (trimmed === '') {
    return { ok: true, value: undefined }
  }
  if (!/^\d+$/.test(trimmed)) {
    return { ok: false, message: 'Enter a whole number, or leave blank to generate one.' }
  }
  const value = Number(trimmed)
  if (!Number.isSafeInteger(value) || value < SEED_MIN || value > SEED_MAX) {
    return { ok: false, message: `The seed must be between ${SEED_MIN} and ${SEED_MAX.toLocaleString('en-US')}.` }
  }
  return { ok: true, value }
}

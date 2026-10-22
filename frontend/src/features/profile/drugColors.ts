/** One colour per antibiotic, in profile order, so a drug is recognised at a glance. Colour is never the only cue: the name is always written. */
const DRUG_COLORS = [
  { fg: '#1d4ed8', bg: '#e8f0ff', border: '#b6ccfa' },
  { fg: '#c2410c', bg: '#fff1e6', border: '#f7c6a0' },
  { fg: '#15803d', bg: '#e4f7ea', border: '#a9dcb8' },
  { fg: '#6d28d9', bg: '#f0eafe', border: '#cfc0f5' },
  { fg: '#0f766e', bg: '#e0f5f2', border: '#a4dcd5' },
  { fg: '#a16207', bg: '#fef6dd', border: '#ecd78a' },
  { fg: '#b91c1c', bg: '#fdeaea', border: '#f1b0b0' },
] as const

export interface DrugColor {
  fg: string
  bg: string
  border: string
}

const FALLBACK: DrugColor = { fg: '#334155', bg: '#eef2f7', border: '#c9d3e1' }

export function drugColor(index: number): DrugColor {
  return DRUG_COLORS[index] ?? FALLBACK
}

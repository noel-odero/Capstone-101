/**
 * Scene palette, matched to the reference visuals: an indigo-violet E. coli rod, cyan and violet capsules, pale blue
 * bubbles, and green/red status markers on a deep navy panel. Status colours are always paired with a letter and a shape.
 */
export const SCENE_COLORS = {
  bacterium: '#5558e8',
  bacteriumDeep: '#3b3fb8',
  bacteriumBump: '#8e93ff',
  bacteriumRim: '#c4b5fd',
  smallBacterium: '#6d4fd6',
  capsuleCyan: '#38bdf8',
  capsuleCyanLight: '#bae6fd',
  capsuleBlue: '#3b82f6',
  capsuleViolet: '#8b5cf6',
  capsuleVioletLight: '#ede9fe',
  bubble: '#a5b8ff',
  panel: '#0b1326',
  susceptible: '#4ade80',
  susceptibleGlow: '#22c55e',
  resistant: '#f87171',
  resistantGlow: '#ef4444',
  changed: '#fbbf24',
  link: '#6b7bb8',
} as const

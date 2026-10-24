import type { ResistanceProfile, StepTrace, StrategyResult } from '@/domain/types'

export type EvaluationPhase = 'initial' | 'action' | 'outcome'
export interface PlaybackState {
  step: number
  phase: EvaluationPhase
  playing: boolean
  speed: number
  completed: boolean
  last: number
}
export type PlaybackAction =
  | { type: 'play' | 'pause' | 'advance' | 'previous' | 'reset' }
  | { type: 'seek'; step: number }
  | { type: 'speed'; speed: number }

export function initialPlayback(last: number, autoPlay = false, step = 0): PlaybackState {
  const selected = Math.max(0, Math.min(last, Number.isInteger(step) ? step : 0))
  return {
    step: selected,
    phase: selected === 0 ? 'initial' : 'outcome',
    playing: autoPlay && last > 0 && selected < last,
    speed: 1,
    completed: selected === last,
    last,
  }
}

export function playbackReducer(state: PlaybackState, action: PlaybackAction): PlaybackState {
  switch (action.type) {
    case 'pause':
      return { ...state, playing: false }
    case 'reset':
      return { ...initialPlayback(state.last), speed: state.speed }
    case 'speed':
      return [0.5, 1, 2].includes(action.speed) ? { ...state, speed: action.speed } : state
    case 'seek': {
      const step = Math.max(0, Math.min(state.last, action.step))
      return Number.isInteger(step)
        ? {
            ...state,
            step,
            phase: step === 0 ? 'initial' : 'outcome',
            playing: false,
            completed: state.completed || step === state.last,
          }
        : state
    }
    case 'previous':
      return playbackReducer(state, { type: 'seek', step: state.step - 1 })
    case 'play':
      return state.last === 0
        ? state
        : state.step === state.last && state.phase === 'outcome'
          ? { ...initialPlayback(state.last, true), speed: state.speed }
          : { ...state, playing: true }
    case 'advance': {
      if (state.last === 0) return { ...state, playing: false, completed: true }
      if (state.phase === 'action')
        return {
          ...state,
          phase: 'outcome',
          completed: state.completed || state.step === state.last,
          playing: state.playing && state.step < state.last,
        }
      if (state.step >= state.last) return { ...state, playing: false }
      return { ...state, step: state.step + 1, phase: 'action' }
    }
  }
}

export interface EvaluationFrame {
  profile: ResistanceProfile
  before: ResistanceProfile
  trace: StepTrace | undefined
  applied: boolean
  ended: boolean
  actualStep: number
}

export function evaluationFrame(
  result: StrategyResult,
  step: number,
  phase: EvaluationPhase,
): EvaluationFrame {
  const trace = result.steps.find((item) => item.treatmentStepAfter === step)
  const applied = phase === 'outcome' && Boolean(trace)
  const available = result.states.filter((state) => state.stateIndex <= step).at(-1)
  const profile =
    step === 0
      ? result.initialProfile
      : trace
        ? applied
          ? trace.resistanceProfileAfter
          : trace.resistanceProfileBefore
        : (available?.resistanceProfile ?? result.finalProfile)
  const last = Math.max(0, ...result.steps.map((item) => item.treatmentStepAfter))
  return {
    profile,
    before: trace?.resistanceProfileBefore ?? profile,
    trace,
    applied,
    ended: last === 0 || step > last || (step === last && phase === 'outcome'),
    actualStep: Math.min(step, last),
  }
}

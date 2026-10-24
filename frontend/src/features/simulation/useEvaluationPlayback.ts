import { useEffect, useReducer } from 'react'
import { prefersReducedMotion } from '@/features/scene/sceneSupport'
import { initialPlayback, playbackReducer } from './evaluation-playback'

export function useEvaluationPlayback(last: number, autoPlay: boolean, step: number) {
  const [state, dispatch] = useReducer(playbackReducer, undefined, () =>
    initialPlayback(last, autoPlay && !prefersReducedMotion(), step),
  )
  useEffect(() => {
    if (!state.playing) return
    const delay = state.phase === 'initial' ? 900 : state.phase === 'action' ? 1100 : 1500
    const timer = window.setTimeout(() => dispatch({ type: 'advance' }), delay / state.speed)
    return () => window.clearTimeout(timer)
  }, [state.playing, state.step, state.phase, state.speed])
  return { state, dispatch }
}

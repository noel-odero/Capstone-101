import { useSearchParams } from 'react-router'

/** The selected step lives in the URL (`?step=3`), so a refresh or a shared link keeps it. */
export function useStepParam(defaultStep = 1): [number, (step: number) => void] {
  const [params, setParams] = useSearchParams()
  const raw = Number(params.get('step'))
  const step = Number.isInteger(raw) && raw >= 0 && raw <= 8 ? raw : defaultStep
  return [
    step,
    (next) => {
      const nextParams = new URLSearchParams(params)
      nextParams.set('step', String(next))
      setParams(nextParams, { replace: true })
    },
  ]
}

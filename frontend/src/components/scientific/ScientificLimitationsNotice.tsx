import { Info } from 'lucide-react'
import { Link } from 'react-router'
import { LIMITATIONS_PATH } from '@/config/navigation'
import { GLOSSARY, PROTOTYPE_STATEMENT } from '@/domain/terminology'
import styles from './scientific.module.css'

export interface ScientificLimitationsNoticeProps {
  /** The full list, used once on the Overview; elsewhere a one-line notice linking to it. */
  detailed?: boolean
  id?: string
}

const LIMITATIONS: readonly string[] = [
  'The simulation is simplified: binary resistance to seven antibiotics, a fixed horizon, and one transition-data scenario. The horizon is a computational parameter, not a treatment duration.',
  'Susceptible means susceptible in the simulated profile. It is not clinical efficacy, and an action that is feasible under the action mask is not necessarily supported by transition data.',
  GLOSSARY.unsupported,
  'A result is one stochastic run from one frozen checkpoint. It does not show that PPO or the baseline is better in general, and it is not evidence about real patients.',
  GLOSSARY.sameSeed,
  'The Random Susceptible Baseline samples uniformly among susceptible antibiotics. It is not an exhaustive or optimal search of antibiotic sequences.',
  'Nothing here is clinically validated. The application uses no patient data and must not be used to choose antibiotics for anyone.',
]

export function ScientificLimitationsNotice({ detailed = false, id }: ScientificLimitationsNoticeProps) {
  return (
    <div className={styles['notice']} role="note" id={id}>
      <Info size={18} aria-hidden="true" />
      <div className={styles['noticeBody']}>
        {detailed ? (
          <>
            <strong>Scientific scope and limitations</strong>
            <p>{PROTOTYPE_STATEMENT}</p>
            <ul className={styles['limitationList']}>
              {LIMITATIONS.map((limitation) => (
                <li key={limitation}>{limitation}</li>
              ))}
            </ul>
          </>
        ) : (
          <p>
            {PROTOTYPE_STATEMENT} <Link to={LIMITATIONS_PATH}>Scope and limitations</Link>
          </p>
        )}
      </div>
    </div>
  )
}

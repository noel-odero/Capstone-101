import { REPOSITORY_URL } from '@/config/navigation'
import { GLOSSARY, STRATEGY_DESCRIPTIONS, STRATEGY_NAMES } from '@/domain/terminology'
import { PublicPage } from './PublicPage'

export function MethodologyPage() {
  return (
    <PublicPage
      title="Methodology"
      lede="What the simulation models, how the two strategies act, and what each metric means."
    >
      <section>
        <h2>The simulation</h2>
        <ul>
          <li>
            The state is binary resistance (susceptible or resistant) to seven antibiotics, so 128
            possible profiles.
          </li>
          <li>
            An episode lasts up to eight steps. At each step a strategy selects one antibiotic.
          </li>
          <li>
            Only antibiotics that are susceptible in the current state may be selected (the action
            mask).
          </li>
          <li>
            After an action the simulator samples one modeled outcome from the candidate transitions
            for that action and state.
          </li>
          <li>If every antibiotic is resistant, no action is feasible and the episode ends.</li>
        </ul>
      </section>
      <section>
        <h2>The strategies</h2>
        <p>
          <strong>{STRATEGY_NAMES.ppo}.</strong> {STRATEGY_DESCRIPTIONS.ppo}
        </p>
        <p>
          <strong>{STRATEGY_NAMES.random_susceptible_baseline}.</strong>{' '}
          {STRATEGY_DESCRIPTIONS.random_susceptible_baseline}
        </p>
      </section>
      <section>
        <h2>Three things kept apart</h2>
        <ul>
          <li>
            <strong>Action selection.</strong> {GLOSSARY.feasible}
          </li>
          <li>
            <strong>Transition support.</strong> {GLOSSARY.transitionSupport}
          </li>
          <li>
            <strong>Simulated outcome.</strong> {GLOSSARY.observedOutcome}
          </li>
        </ul>
        <p>{GLOSSARY.unsupported}</p>
      </section>
      <section>
        <h2>Metrics</h2>
        <ul>
          <li>
            <strong>Cumulative resistance burden.</strong> The sum over steps of resistant
            antibiotics divided by seven, with an all-resistant state charged for the rest of the
            horizon. Lower is less simulated burden.
          </li>
          <li>
            <strong>Resistance-emergence events.</strong> {GLOSSARY.resistanceEmergence}
          </li>
          <li>
            <strong>Remaining susceptible options.</strong> Antibiotics still susceptible at the
            end.
          </li>
          <li>
            <strong>Susceptible-action rate.</strong> The share of steps whose selected antibiotic
            was susceptible. The action mask makes it 1.0 for both strategies, so it is not a
            measure of effectiveness.
          </li>
        </ul>
        <p>Each result carries the simulator&apos;s own definition of every metric it reports.</p>
      </section>
      <section>
        <h2>Specification</h2>
        <p>
          The full specification is in the repository:{' '}
          <a
            href={`${REPOSITORY_URL}/tree/main/docs/scientific-specification`}
            rel="noreferrer noopener"
            target="_blank"
          >
            docs/scientific-specification
          </a>
          .
        </p>
      </section>
    </PublicPage>
  )
}

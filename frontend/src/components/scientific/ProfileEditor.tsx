import { useId, useState } from 'react'
import { ResistanceProfileGrid } from '@/components/scientific/ResistanceProfileGrid'
import { Button } from '@/components/ui/Button'
import type { AntibioticEntry } from '@/domain/antibiotics'
import { allResistantProfile, allSusceptibleProfile, parseProfileCode, profileToCode, profilesEqual, toggleAntibiotic } from '@/domain/profile'
import type { ResistanceProfile } from '@/domain/types'
import styles from './profile-editor.module.css'

export interface ProfileEditorProps {
  entries: readonly AntibioticEntry[]
  profile: ResistanceProfile
  onChange: (profile: ResistanceProfile) => void
  /** Show the reset control only when the profile differs from this one. */
  resetTo?: ResistanceProfile | undefined
}

/** Seven toggles, two documented presets and a code field covering all 128 profiles. The parent owns the profile. */
export function ProfileEditor({ entries, profile, onChange, resetTo }: ProfileEditorProps) {
  const inputId = useId()
  const hintId = useId()
  const code = profileToCode(profile)
  const [draft, setDraft] = useState<string | null>(null)
  const invalid = draft !== null && parseProfileCode(draft) === null

  const onCodeChange = (value: string) => {
    const parsed = parseProfileCode(value)
    if (parsed) {
      setDraft(null)
      onChange(parsed)
    } else {
      setDraft(value)
    }
  }

  const susceptible = allSusceptibleProfile()
  const resistant = allResistantProfile()

  return (
    <div className="stack">
      <div className={styles['presets']} role="group" aria-label="Profile presets">
        <Button variant="secondary" size="sm" aria-pressed={profilesEqual(profile, susceptible)} onClick={() => onChange(susceptible)}>
          All susceptible
        </Button>
        <Button variant="secondary" size="sm" aria-pressed={profilesEqual(profile, resistant)} onClick={() => onChange(resistant)}>
          All resistant
        </Button>
        {resetTo && !profilesEqual(profile, resetTo) ? (
          <Button variant="ghost" size="sm" onClick={() => onChange(resetTo)}>
            Reset
          </Button>
        ) : null}
      </div>
      <ResistanceProfileGrid
        label="Resistance profile"
        entries={entries}
        profile={profile}
        onToggle={(index) => onChange(toggleAntibiotic(profile, index))}
      />
      <div>
        <label className={styles['label']} htmlFor={inputId}>
          Profile code
        </label>
        <input
          id={inputId}
          className={styles['input']}
          value={draft ?? code}
          inputMode="numeric"
          maxLength={7}
          autoComplete="off"
          spellCheck={false}
          aria-invalid={invalid}
          aria-describedby={hintId}
          onChange={(event) => onCodeChange(event.target.value)}
          onBlur={() => setDraft(null)}
        />
        <p id={hintId} className={invalid ? styles['error'] : styles['hint']}>
          {invalid ? 'Enter seven digits, each 0 or 1.' : '0 susceptible, 1 resistant, in the order shown.'}
        </p>
      </div>
    </div>
  )
}

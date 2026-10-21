import * as ToggleGroup from '@radix-ui/react-toggle-group'
import { FiMonitor, FiMoon, FiSun } from 'react-icons/fi'
import { setThemePreference, useThemePreference, type ThemePreference } from '@/app/theme'
import styles from './ui.module.css'

const options = [
  { value: 'light', label: 'Light theme', icon: FiSun },
  { value: 'dark', label: 'Dark theme', icon: FiMoon },
  { value: 'system', label: 'System theme', icon: FiMonitor },
] as const

export function ThemeControl({
  value,
  onChange,
}: {
  value?: ThemePreference | undefined
  onChange?: ((value: ThemePreference) => void) | undefined
} = {}) {
  const preference = useThemePreference()
  return (
    <ToggleGroup.Root
      type="single"
      value={value ?? preference}
      onValueChange={(value) => {
        if (value) (onChange ?? setThemePreference)(value as ThemePreference)
      }}
      aria-label="Appearance"
      className={styles['themeControl']}
    >
      {options.map(({ value, label, icon: Icon }) => (
        <ToggleGroup.Item
          key={value}
          value={value}
          aria-label={label}
          title={label}
          className={styles['themeOption']}
        >
          <Icon size={15} aria-hidden="true" />
        </ToggleGroup.Item>
      ))}
    </ToggleGroup.Root>
  )
}

import type { ElementType, HTMLAttributes, ReactNode } from 'react'
import { cx } from './cx'
import styles from './ui.module.css'

export interface CardProps extends HTMLAttributes<HTMLElement> {
  as?: ElementType
  tone?: 'default' | 'subtle' | 'emphasis'
  flush?: boolean
}

export function Card({ as: Tag = 'section', tone = 'default', flush = false, className, ...rest }: CardProps) {
  return (
    <Tag
      {...rest}
      className={cx(
        styles['card'],
        tone === 'subtle' && styles['cardSubtle'],
        tone === 'emphasis' && styles['cardEmphasis'],
        flush && styles['cardFlush'],
        className,
      )}
    />
  )
}

export interface CardHeaderProps {
  title: ReactNode
  description?: ReactNode
  /** Heading element id, so a section can be labelled by it. */
  titleId?: string
  headingLevel?: 'h2' | 'h3'
  actions?: ReactNode
}

export function CardHeader({ title, description, titleId, headingLevel: Heading = 'h2', actions }: CardHeaderProps) {
  return (
    <div className={styles['cardHeader']}>
      <div className={styles['cardHeading']}>
        <Heading id={titleId} className={styles['cardTitle']}>
          {title}
        </Heading>
        {description ? <p className={styles['cardDescription']}>{description}</p> : null}
      </div>
      {actions}
    </div>
  )
}

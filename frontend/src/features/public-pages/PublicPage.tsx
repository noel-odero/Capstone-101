import { ContentContainer } from '@/components/layout/ContentContainer'
import { APP_NAME } from '@/domain/terminology'
import { useEffect, type ReactNode } from 'react'
import styles from './public-pages.module.css'

export function PublicPage({
  title,
  lede,
  children,
  visual,
  eyebrow,
}: {
  title: string
  lede: string
  children: ReactNode
  visual?: ReactNode
  eyebrow?: string
}) {
  useEffect(() => {
    document.title = `${title} \u00b7 ${APP_NAME}`
  }, [title])

  return (
    <ContentContainer>
      <div className={styles['page']}>
        <article className={`${styles.article} ${visual ? styles.editorial : ''}`}>
          <header className={visual ? styles.hero : 'stack'}>
            <div className={visual ? styles.heroCopy : 'stack'}>
              {eyebrow ? <p className={styles.eyebrow}>{eyebrow}</p> : null}
              <h1>{title}</h1>
              <p className={styles['lede']}>{lede}</p>
            </div>
            {visual}
          </header>
          {children}
        </article>
      </div>
    </ContentContainer>
  )
}

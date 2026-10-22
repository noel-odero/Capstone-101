import { ContentContainer } from '@/components/layout/ContentContainer'
import { APP_NAME } from '@/domain/terminology'
import { useEffect, type ReactNode } from 'react'
import styles from './public-pages.module.css'

export function PublicPage({
  title,
  lede,
  children,
}: {
  title: string
  lede: string
  children: ReactNode
}) {
  useEffect(() => {
    document.title = `${title} \u00b7 ${APP_NAME}`
  }, [title])

  return (
    <ContentContainer>
      <div className={styles['page']}>
        <article className={styles['article']}>
          <header className="stack">
            <h1>{title}</h1>
            <p className={styles['lede']}>{lede}</p>
          </header>
          {children}
        </article>
      </div>
    </ContentContainer>
  )
}

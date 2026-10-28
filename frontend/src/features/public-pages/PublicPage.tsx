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
    document.title = `${title} · ${APP_NAME}`
  }, [title])

  return (
    <ContentContainer>
      <article className={styles.page}>
        <header className={styles.header}>
          <h1>{title}</h1>
          <p className={styles.lede}>{lede}</p>
        </header>
        <div className={styles.article}>{children}</div>
      </article>
    </ContentContainer>
  )
}

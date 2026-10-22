import { chromium } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

// Read-only browser check against the running app. No mocked responses or account creation.
const baseURL = process.env.AMR_UI_URL ?? 'http://127.0.0.1:5173'
const output = new URL('../playwright-report/landing-live/', import.meta.url)
await mkdir(output, { recursive: true })
const browser = await chromium.launch()
try {
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1050 },
    colorScheme: 'light',
    reducedMotion: 'reduce',
  })
  const errors = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto(baseURL)
  await page
    .getByRole('heading', { name: 'Explore the future of antibiotic resistance.', exact: true })
    .waitFor()
  if (await page.getByAltText(/Actual workbench interface/).count())
    throw new Error('Workbench preview must not appear on landing')
  await page.evaluate(() => document.fonts.ready)
  await page.waitForLoadState('networkidle')
  await page.evaluate(() => scrollTo(0, 0))
  await page.screenshot({
    path: fileURLToPath(new URL('desktop-dark.png', output)),
    fullPage: true,
  })
  await page.getByRole('button', { name: 'Switch landing page to light mode' }).click()
  await page.screenshot({
    path: fileURLToPath(new URL('desktop-light.png', output)),
    fullPage: true,
  })
  await page.getByRole('button', { name: 'Switch landing page to dark mode' }).click()
  await page.setViewportSize({ width: 390, height: 844 })
  await page.waitForFunction(() => document.documentElement.scrollWidth <= innerWidth)
  await page.screenshot({ path: fileURLToPath(new URL('mobile.png', output)), fullPage: true })
  if (errors.length) throw new Error(errors.join('\n'))
  console.log(
    'Live landing passed: desktop dark/light, mobile, no workbench preview, no browser errors. Screenshots: playwright-report/landing-live/',
  )
} finally {
  await browser.close()
}

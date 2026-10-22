import { chromium } from '@playwright/test'
import { randomUUID } from 'node:crypto'
import { mkdir } from 'node:fs/promises'

// Opt-in live smoke check: creates a disposable account and run in the configured local backend.
// Run only against a local preview database, with all three services already running.
const baseURL = process.env.AMR_UI_URL ?? 'http://127.0.0.1:5173'
const health = await fetch(`${baseURL}/api/v1/health`).then((response) => response.json())
if (!health.ready) throw new Error(`Backend not ready: ${JSON.stringify(health)}`)
const browser = await chromium.launch()
const context = await browser.newContext({
  viewport: { width: 1280, height: 900 },
  colorScheme: 'light',
  reducedMotion: 'reduce',
})
const page = await context.newPage()
const errors = []
page.on('pageerror', (error) => errors.push(error.message))
const output = new URL('../playwright-report/live-preview/', import.meta.url)
await mkdir(output, { recursive: true })
try {
  await page.goto(`${baseURL}/auth/register`)
  await page.getByLabel(/^Name/).fill('Angie Preview')
  await page.getByLabel('Email', { exact: true }).fill(`ui-preview-${randomUUID()}@example.test`)
  await page.getByLabel('Password', { exact: true }).fill(`Preview!${randomUUID()}`)
  await page.getByRole('button', { name: 'Create account', exact: true }).click()
  await page.waitForURL('**/app', { timeout: 30000 })
  await page.goto(`${baseURL}/app/simulation/new`)
  await page.getByRole('button', { name: 'Run Simulation', exact: true }).click()
  await page.waitForURL(/\/app\/simulation\/[a-f0-9-]+$/, { timeout: 60000 })
  const simulationURL = page.url()
  await page.getByRole('heading', { name: 'Urinary Tract', exact: true }).waitFor()
  await page.getByRole('button', { name: 'Step 3', exact: true }).click()
  if (
    (await page
      .getByRole('button', { name: 'Step 3', exact: true })
      .getAttribute('aria-pressed')) !== 'true'
  )
    throw new Error('Timeline did not update')
  const urls = [
    ['home', '/app'],
    ['simulation', new URL(simulationURL).pathname],
    ['recommendations', '/app/recommendations'],
    ['profile', '/app/profile'],
  ]
  for (const [name, url] of urls) {
    await page.goto(`${baseURL}${url}`)
    await page.waitForLoadState('networkidle')
    await page.evaluate(() => document.fonts.ready)
    await page.screenshot({
      path: new URL(`${name}-desktop.png`, output).pathname.replace(/^\/([A-Za-z]:)/, '$1'),
      fullPage: true,
    })
    await page.setViewportSize({ width: 390, height: 844 })
    // Recharts measures its parent through ResizeObserver after the viewport changes.
    await page.waitForFunction(() => document.documentElement.scrollWidth <= innerWidth)
    if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth))
      throw new Error(`${name} overflows on mobile`)
    await page.screenshot({
      path: new URL(`${name}-mobile.png`, output).pathname.replace(/^\/([A-Za-z]:)/, '$1'),
      fullPage: true,
    })
    await page.setViewportSize({ width: 1280, height: 900 })
  }
  if (errors.length) throw new Error(errors.join('\n'))
  console.log(
    'Live UI passed: registration, real PPO comparison, timeline, four desktop/mobile screens, no browser errors. Screenshots: frontend/playwright-report/live-preview/',
  )
} finally {
  await browser.close()
}

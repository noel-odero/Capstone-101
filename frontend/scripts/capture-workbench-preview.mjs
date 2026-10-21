import { chromium } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

// Capture the real UI with captured scientific responses. No runtime mock mode or patient data.
const fixture = async (name) =>
  JSON.parse(
    await readFile(new URL(`../src/test/fixtures/captured/${name}.json`, import.meta.url), 'utf8'),
  )
const comparison = await fixture('comparison')
const bodies = {
  'auth/session': {
    isAuthenticated: true,
    user: { displayName: 'Research workspace', email: 'research@example.test' },
    csrfToken: 'preview-token',
  },
  health: await fixture('health'),
  model: await fixture('model'),
  antibiotics: await fixture('antibiotics'),
  'simulations/recent': await fixture('recent-runs'),
}
const browser = await chromium.launch()
try {
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1050 },
    colorScheme: 'light',
    reducedMotion: 'reduce',
  })
  await page.addInitScript(() => localStorage.setItem('amr.theme', 'light'))
  await page.route('**/api/v1/**', async (route) => {
    const resource = new URL(route.request().url()).pathname.replace('/api/v1/', '')
    const body =
      bodies[resource] ??
      (resource.startsWith('comparisons/')
        ? { ...comparison, id: resource.split('/')[1] }
        : undefined)
    await route.fulfill({
      status: body ? 200 : 404,
      contentType: 'application/json',
      body: JSON.stringify(body ?? {}),
    })
  })
  await page.goto(
    `${process.env.AMR_UI_URL ?? 'http://127.0.0.1:5173'}/app/simulation/${comparison.id}`,
  )
  await page.getByRole('heading', { name: 'Simulation', exact: true }).waitFor()
  await page.locator('[data-visual-particles] canvas').waitFor({ timeout: 60000 })
  await page.evaluate(() => document.fonts.ready)
  await page.waitForLoadState('networkidle')
  await page.screenshot({
    path: fileURLToPath(new URL('../public/images/workbench-preview.png', import.meta.url)),
  })
  console.log('Captured actual workbench UI: public/images/workbench-preview.png')
} finally {
  await browser.close()
}

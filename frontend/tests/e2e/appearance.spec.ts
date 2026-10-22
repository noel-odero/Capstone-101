import { expect, test, type Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import path from 'node:path'

const fixture = (name: string) =>
  JSON.parse(
    readFileSync(path.join(process.cwd(), 'src/test/fixtures/captured', `${name}.json`), 'utf8'),
  )
const comparison = fixture('comparison')
const recent = fixture('recent-runs')
const comparisonId = comparison.id as string

/** Captured scientific responses are intercepted only in tests; no runtime mock mode is introduced. */
async function mockApi(page: Page) {
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url())
    const resource = url.pathname.replace('/api/v1/', '')
    const bodies: Record<string, unknown> = {
      'auth/session': {
        isAuthenticated: true,
        user: { displayName: 'Ada Researcher', email: 'ada@example.org' },
        csrfToken: 'test-token',
      },
      health: fixture('health'),
      model: fixture('model'),
      antibiotics: fixture('antibiotics'),
      'simulations/recent': recent,
      'profiles/validate': fixture('profile-validation'),
      comparisons: comparison,
    }
    const body =
      bodies[resource] ??
      (resource.startsWith('comparisons/')
        ? { ...comparison, id: resource.split('/')[1] }
        : resource.startsWith('simulations/')
          ? fixture('simulation-ppo')
          : undefined)
    await route.fulfill({
      status: body ? 200 : 404,
      contentType: 'application/json',
      body: JSON.stringify(body ?? { code: 'not_found' }),
    })
  })
}

test.setTimeout(90_000)

test.beforeEach(async ({ page }) => {
  await mockApi(page)
})

for (const [width, height] of [
  [1280, 720],
  [1366, 768],
  [1536, 864],
]) {
  test(`laptop layouts fit at ${width} by ${height}`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width: width!, height: height! })
    await page.emulateMedia({ reducedMotion: 'reduce' })
    for (const [name, url] of [
      ['home', '/app'],
      ['setup', '/app/simulation/new'],
      ['simulation', `/app/simulation/${comparisonId}`],
      ['recommendations', `/app/recommendations/comparison/${comparisonId}`],
      ['profile', '/app/profile'],
      ['history', '/app/history'],
      ['landing', '/'],
    ]) {
      await page.goto(url!)
      await expect(page.locator('h1')).toBeVisible()
      await page.waitForLoadState('networkidle')
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
        width!,
      )
      if (name === 'home' || name === 'setup') {
        const action = page.getByRole(name === 'home' ? 'link' : 'button', {
          name: name === 'home' ? 'Open Workbench' : 'Review simulation',
          exact: true,
        })
        const bounds = await action.boundingBox()
        expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(height!)
      }
      await page.screenshot({ path: testInfo.outputPath(`${name}.png`), fullPage: true })
    }
  })
}

test('simulation configuration toggles, reviews and submits the selected profile', async ({
  page,
}, testInfo) => {
  await page.goto('/app/simulation/new')
  await expect(page.getByRole('heading', { name: 'Configure your simulation' })).toBeVisible()
  await expect(page.getByRole('switch')).toHaveCount(7)
  await expect(page.getByRole('combobox')).toHaveCount(0)
  await page.getByRole('switch', { name: 'Ciprofloxacin resistant' }).click()
  await expect(page.getByLabel('Resistance profile code')).toHaveText('1000000')
  await expect(page.getByText('1 / 7 resistant')).toBeVisible()
  await page.getByRole('button', { name: 'Reset', exact: true }).click()
  await expect(page.getByLabel('Resistance profile code')).toHaveText('0000000')
  for (const toggle of await page.getByRole('switch').all()) await toggle.click()
  await expect(page.getByRole('button', { name: 'Review simulation', exact: true })).toBeDisabled()
  await page.getByRole('switch', { name: 'Ciprofloxacin resistant' }).click()
  await page.getByRole('button', { name: 'Review simulation', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Review your simulation' })).toBeVisible()
  await expect(page.getByRole('switch').first()).toBeDisabled()
  await page.getByRole('button', { name: 'Edit configuration' }).click()
  await expect(page.getByRole('switch').first()).toBeEnabled()
  await page.getByRole('button', { name: 'Reset', exact: true }).click()
  await page.getByRole('switch', { name: 'Nitrofurantoin resistant' }).click()
  await page.screenshot({ path: testInfo.outputPath('configure-desktop.png'), fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
  await page.screenshot({ path: testInfo.outputPath('configure-mobile.png'), fullPage: true })
  await page.getByRole('button', { name: 'Review simulation', exact: true }).click()
  const request = page.waitForRequest(
    (request) => request.url().endsWith('/api/v1/comparisons') && request.method() === 'POST',
  )
  await page.getByRole('button', { name: 'Run Simulation', exact: true }).click()
  expect((await request).postDataJSON()).toEqual({ resistanceProfile: [0, 1, 0, 0, 0, 0, 0] })
  await expect(page).toHaveURL(/\/app\/simulation\/[0-9a-f-]{36}$/)
  await expect(page.getByRole('heading', { name: 'Simulation', exact: true })).toBeVisible()
})

test('home introduces the workbench journey before the sequence panel', async ({
  page,
}, testInfo) => {
  await page.goto('/app')
  const journey = page.getByRole('region', {
    name: 'Explore the workbench',
  })
  await expect(journey).toBeVisible()
  await expect(journey.getByRole('heading', { name: 'Build scenarios' })).toHaveCSS(
    'color',
    'rgb(36, 36, 39)',
  )
  await expect(journey.getByRole('link', { name: /Build scenarios/ })).toHaveAttribute(
    'href',
    '/app/simulation/new',
  )
  await expect(journey.getByRole('link', { name: /Compare strategies/ })).toHaveAttribute(
    'href',
    '/app/simulation',
  )
  await expect(journey.getByRole('link', { name: /Trace outcomes/ })).toHaveAttribute(
    'href',
    '/app/history',
  )
  const panel = page.getByRole('region', { name: 'Launch the Workbench' })
  expect((await panel.boundingBox())!.y).toBeGreaterThan((await journey.boundingBox())!.y)
  await expect(page.getByText('Current Resistance Burden', { exact: true })).toHaveCount(0)
  await page.screenshot({ path: testInfo.outputPath('home-journey-desktop.png'), fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
  await page.screenshot({ path: testInfo.outputPath('home-journey-mobile.png'), fullPage: true })
  await journey.getByRole('link', { name: /Build scenarios/ }).click()
  await expect(
    page.getByRole('heading', { name: 'Configure your simulation', exact: true }),
  ).toBeVisible()
})

test('light and dark appearance persists through navigation and reload', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'light', reducedMotion: 'reduce' })
  await page.goto('/app')
  await expect(page.getByRole('heading', { name: 'Welcome to StewardLab' })).toBeVisible()
  await expect(page.locator('aside')).toHaveCSS('background-color', 'rgb(234, 234, 229)')
  await expect(page.locator('aside')).toHaveCSS('background-image', 'none')
  await page.getByRole('radio', { name: 'Dark theme' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await expect(page.locator('body')).toHaveCSS('background-color', 'rgb(35, 35, 37)')
  await expect(page.locator('aside')).toHaveCSS('background-color', 'rgb(23, 23, 25)')
  await page.getByRole('link', { name: 'E. coli Profile', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'E. coli Profile', exact: true })).toBeVisible()
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await page.getByRole('radio', { name: 'Light theme' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
})

test('system preference follows the operating system', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'dark' })
  await page.goto('/app')
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await page.emulateMedia({ colorScheme: 'light' })
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
})

for (const theme of ['light', 'dark'] as const) {
  test(`${theme} workspace screens render actual fixture results`, async ({ page }, testInfo) => {
    await page.addInitScript((value) => localStorage.setItem('amr.theme', value), theme)
    await page.emulateMedia({ reducedMotion: 'reduce' })
    for (const [name, url, heading] of [
      ['home', '/app', 'Welcome to StewardLab'],
      ['simulation', `/app/simulation/${comparisonId}`, 'Simulation'],
      [
        'sequence',
        `/app/recommendations/comparison/${comparisonId}`,
        'Results and Recommendations',
      ],
      ['profile', '/app/profile', 'E. coli Profile'],
      ['new-experiment', '/app/simulation/new', 'Configure your simulation'],
      ['history', '/app/history', 'Experiment History'],
      ['landing', '/', 'Explore the future of antibiotic resistance.'],
    ] as const) {
      await page.goto(url)
      await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible()
      await expect(page.getByRole('alert')).toHaveCount(0)
      await page.waitForLoadState('networkidle')
      await page.evaluate(() => document.fonts.ready)
      await page.screenshot({ path: testInfo.outputPath(`${name}-${theme}.png`), fullPage: true })
    }
  })
}

test('mobile navigation exposes appearance controls without page overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/app')
  await expect(page.getByRole('heading', { name: 'Welcome to StewardLab' })).toBeVisible()
  await page.getByRole('button', { name: 'Open navigation menu' }).click()
  const drawer = page.getByRole('dialog', { name: 'Navigation menu' })
  await drawer.getByRole('radio', { name: 'Dark theme' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await page.keyboard.press('Escape')
  await expect(drawer).not.toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('simulation shows stored initial conditions and the timeline remains interactive', async ({
  page,
}) => {
  await page.goto(`/app/simulation/${comparisonId}`)
  const initial = page.getByRole('region', { name: 'Initial simulation status' })
  const code = comparison.ppo.initialProfile.join('')
  await expect(initial.locator('code')).toHaveText(code)
  await expect(initial).toContainText(`${comparison.provenance.horizon} steps`)
  await expect(page.getByRole('combobox')).toHaveCount(0)
  await expect(initial.getByRole('link', { name: 'Configure new simulation' })).toHaveAttribute(
    'href',
    `/app/simulation/new?profile=${code}`,
  )
  await page.getByRole('button', { name: 'Step 3', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Step 3', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await page.getByRole('button', { name: 'Play through the steps' }).click()
  await expect(page.getByRole('button', { name: 'Step 4', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await expect(initial.locator('code')).toHaveText(code)
  await initial.getByRole('link', { name: 'Configure new simulation' }).click()
  await expect(page.getByLabel('Resistance profile code')).toHaveText(code)
})

test('all four workspace pages fit a mobile viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  for (const url of [
    '/app',
    `/app/simulation/${comparisonId}`,
    `/app/recommendations/comparison/${comparisonId}`,
    '/app/profile',
  ]) {
    await page.goto(url)
    await expect(page.locator('main h1')).toBeVisible()
    await page.waitForLoadState('networkidle')
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  }
})

test('3D bacteria clear with the timeline and context loss has a readable fallback', async ({
  page,
}, testInfo) => {
  await page.emulateMedia({ reducedMotion: 'no-preference' })
  await page.goto(`/app/simulation/${comparisonId}`)
  const scene = page.locator('[data-visual-particles]')
  await expect(scene.locator('canvas')).toBeVisible({ timeout: 20_000 })
  for (const [step, remaining] of [
    [0, 48],
    [4, 24],
    [8, 0],
  ] as const) {
    await page
      .getByRole('button', {
        name: step === 0 ? 'Step 0, initial state' : `Step ${step}`,
        exact: true,
      })
      .click()
    await expect(scene).toHaveAttribute('data-visual-particles', String(remaining))
    // Allow the dissolve animation to settle before recording the actual WebGL rendering.
    await page.waitForTimeout(1500)
    await scene.screenshot({ path: testInfo.outputPath(`clearance-step-${step}.png`) })
  }
  await scene.locator('canvas').dispatchEvent('webglcontextlost', { cancelable: true })
  await expect(page.getByText('3D view unavailable')).toBeVisible()
  await expect(page.getByText('0 of 48 illustrative bacteria remain at step 8.')).toBeVisible()
})

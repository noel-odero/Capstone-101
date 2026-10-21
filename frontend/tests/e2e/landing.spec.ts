import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ isAuthenticated: false, user: null, csrfToken: 'landing-test' }),
    }),
  )
})

test('research landing is dark by default, has seven nodes and launches through sign-in', async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 1050 })
  await page.emulateMedia({ colorScheme: 'light', reducedMotion: 'reduce' })
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  const scienceRequests: string[] = []
  page.on('request', (request) => {
    if (request.url().includes('/api/v1/') && !request.url().endsWith('/auth/session'))
      scienceRequests.push(request.url())
  })
  await page.goto('/')
  const resources = page.getByRole('navigation', { name: 'Research resources' })
  await expect(resources.getByRole('link', { name: 'Methodology', exact: true })).toHaveAttribute(
    'href',
    '/methodology',
  )
  await expect(resources.getByRole('link', { name: 'Limitations', exact: true })).toHaveAttribute(
    'href',
    '/limitations',
  )
  await expect(resources.getByRole('link', { name: 'Source', exact: true })).toHaveAttribute(
    'target',
    '_blank',
  )
  await expect(page.locator('footer')).toHaveCount(0)
  await expect(page.locator('[data-landing-theme]')).toHaveAttribute('data-landing-theme', 'dark')
  await expect(
    page.getByRole('heading', {
      name: 'Explore the future of antibiotic resistance.',
      exact: true,
    }),
  ).toBeVisible()
  await expect(
    page.getByRole('img', { name: /Seven modeled antibiotics/ }).locator('title'),
  ).toHaveCount(7)
  await expect(page.getByAltText(/Actual workbench interface/)).toHaveCount(0)
  await expect(page.getByRole('heading', { name: /From resistance profiles/ })).toHaveCount(0)
  expect(scienceRequests).toEqual([])
  await page.evaluate(() => document.fonts.ready)
  await page.screenshot({ path: testInfo.outputPath('landing-desktop-dark.png'), fullPage: true })
  expect(errors).toEqual([])
  await page.getByRole('link', { name: 'Launch Workbench', exact: true }).click()
  await expect(page).toHaveURL(/\/auth\/sign-in\?returnTo=%2Fapp$/)
  await expect(page.getByRole('heading', { name: 'Sign in', exact: true })).toBeVisible()
})

test('landing theme is independent from the workbench and animation can pause', async ({
  page,
}, testInfo) => {
  await page.addInitScript(() => localStorage.setItem('amr.theme', 'dark'))
  await page.goto('/')
  await page.getByRole('button', { name: 'Pause network animation' }).click()
  await expect(
    page.getByRole('figure', { name: 'Conceptual seven-antibiotic resistance network' }),
  ).toHaveAttribute('data-paused', 'true')
  await page.getByRole('button', { name: 'Switch landing page to light mode' }).click()
  await expect(page.locator('[data-landing-theme]')).toHaveAttribute('data-landing-theme', 'light')
  expect(await page.evaluate(() => localStorage.getItem('amr.theme'))).toBe('dark')
  await page.screenshot({ path: testInfo.outputPath('landing-desktop-light.png'), fullPage: true })
  await page.getByRole('link', { name: 'Explore the Methodology', exact: true }).first().click()
  await expect(page).toHaveURL(/\/methodology$/)
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
})

for (const width of [390, 768])
  test(`landing fits ${width}px and all primary actions stay accessible`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width, height: 844 })
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.goto('/')
    await expect(page.getByRole('link', { name: 'Launch Workbench', exact: true })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Platform', exact: true })).toBeVisible()
    await page.waitForLoadState('networkidle')
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: testInfo.outputPath(`landing-${width}.png`), fullPage: true })
  })

test('auth pages retain their form layout and share the landing palette', async ({
  page,
}, testInfo) => {
  await page.goto('/')
  await page.getByRole('link', { name: 'Launch Workbench', exact: true }).click()
  const palette = page.locator('[data-auth-theme]')
  await expect(palette).toHaveAttribute('data-auth-theme', 'dark')
  await expect(page.getByLabel('Email', { exact: true })).toBeVisible()
  await expect(page.getByText('Email', { exact: true })).toHaveCSS('color', 'rgb(247, 248, 252)')
  await expect(page.getByLabel('Email', { exact: true })).toHaveCSS(
    'background-color',
    'rgb(17, 23, 43)',
  )
  await page.screenshot({ path: testInfo.outputPath('sign-in-dark.png'), fullPage: true })
  await page.getByRole('radio', { name: 'Light theme', exact: true }).click()
  await expect(palette).toHaveAttribute('data-auth-theme', 'light')
  await page.screenshot({ path: testInfo.outputPath('sign-in-light.png'), fullPage: true })
  await page.goto('/auth/register')
  await expect(page.getByRole('heading', { name: 'Create an account', exact: true })).toBeVisible()
  await expect(palette).toHaveAttribute('data-auth-theme', 'dark')
  await expect(page.getByLabel('Email', { exact: true })).toHaveCSS(
    'background-color',
    'rgb(17, 23, 43)',
  )
  await page.screenshot({ path: testInfo.outputPath('sign-up-dark.png'), fullPage: true })
})

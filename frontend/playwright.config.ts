import { defineConfig, devices } from '@playwright/test'

// Keep browser checks isolated from a developer's existing Vite session.
const baseURL = 'http://127.0.0.1:5177'

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',
  use: { baseURL, trace: 'retain-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'node ./node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5177 --strictPort',
    url: baseURL,
    reuseExistingServer: false,
    timeout: 60_000,
  },
})

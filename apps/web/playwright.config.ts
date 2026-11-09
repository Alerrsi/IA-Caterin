import { defineConfig, devices } from '@playwright/test'

/**
 * E2E contra el compose de desarrollo levantado (web en :5173, API y Postgres con el seed de demo).
 * Usa el Chromium del sistema: PW_CHROMIUM=/ruta/al/chromium (por defecto /usr/bin/chromium).
 *   npx playwright test
 */
export default defineConfig({
  testDir: './e2e',
  testMatch: '*.e2e.ts',
  timeout: 60_000,
  outputDir: 'test-results',
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5173',
    ...devices['Pixel 7'],
    viewport: { width: 390, height: 844 },
    launchOptions: { executablePath: process.env.PW_CHROMIUM ?? '/usr/bin/chromium' },
    locale: 'es-CL',
  },
  projects: [{ name: 'movil' }],
})

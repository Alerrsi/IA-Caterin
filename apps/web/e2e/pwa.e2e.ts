import { expect, test } from '@playwright/test'

/**
 * ADR-004: con la build de producción (service worker), la app abre SIN red y muestra lo guardado.
 * Corre solo contra `vite preview`:  npm run build && npx vite preview --port 4173 &
 *   PWA_BASE_URL=http://localhost:4173 npx playwright test e2e/pwa.e2e.ts
 */
const BASE = process.env.PWA_BASE_URL
const EMAIL = process.env.E2E_EMAIL ?? 'duena.aromos@demo.local'
const PASSWORD = process.env.E2E_PASSWORD ?? 'caterin-demo-2026'

test.skip(!BASE, 'requiere PWA_BASE_URL (build + vite preview)')

test('sin red: abre la app con la sesión recordada y muestra el inventario guardado', async ({ page, context }) => {
  await page.goto(`${BASE}/`)
  await page.getByLabel('Correo').fill(EMAIL)
  await page.getByLabel('Contraseña').fill(PASSWORD)
  await page.getByRole('button', { name: 'Entrar' }).click()
  await expect(page.getByRole('heading', { name: /Hola/ })).toBeVisible()
  await page.evaluate(() => navigator.serviceWorker.ready.then(() => true))
  await page.goto(`${BASE}/#/inventario`)
  await expect(page.getByText('Sal', { exact: true })).toBeVisible()

  await context.setOffline(true)
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Inventario' })).toBeVisible()
  await expect(page.getByText(/Sin conexión: datos guardados/)).toBeVisible()
  await expect(page.getByText('Sal', { exact: true })).toBeVisible()
  await page.goto(`${BASE}/#/`)
  await expect(page.getByRole('heading', { name: /Hola/ })).toBeVisible()
  await page.screenshot({ path: 'e2e-artifacts/offline-inicio-390.png', fullPage: true })
  await context.setOffline(false)
})

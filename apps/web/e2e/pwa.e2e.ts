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

test('la PWA instalable trae los íconos de la marca y las fuentes funcionan sin red (T14)', async ({ page, context }) => {
  const manifest = await (await page.request.get(`${BASE}/manifest.webmanifest`)).json()
  const purposes = manifest.icons.map((i: { src: string; purpose: string }) => `${i.src}:${i.purpose}`)
  expect(purposes).toEqual(expect.arrayContaining(['pwa-512.png:any', 'pwa-maskable-512.png:maskable']))
  expect(manifest.theme_color).toBe('#6d2a57')

  await page.goto(`${BASE}/`)
  await page.evaluate(() => navigator.serviceWorker.ready.then(() => true))
  await context.setOffline(true)
  await page.reload()
  await expect(page.getByRole('heading', { level: 1, name: 'Cáterin' })).toBeVisible()
  const loaded = await page.evaluate(async () => {
    await document.fonts.ready
    return [...document.fonts].filter((f) => f.status === 'loaded').map((f) => f.family)
  })
  expect(loaded).toEqual(expect.arrayContaining(['Roboto', 'Bricolage Grotesque Variable']))
  await context.setOffline(false)
})

test('sin red: el cliente vuelve a ver el catálogo de una pyme con su logo (T15)', async ({ page, context }) => {
  await page.goto(`${BASE}/`)
  await page.getByLabel('Correo').fill(process.env.E2E_CUSTOMER ?? 'cliente1.llaima@demo.local')
  await page.getByLabel('Contraseña').fill(PASSWORD)
  await page.getByRole('button', { name: 'Entrar' }).click()
  await page.evaluate(() => navigator.serviceWorker.ready.then(() => true))
  await page.goto(`${BASE}/#/pymes`)
  await page.getByRole('link', { name: /Volcán Llaima/ }).click()
  await expect(page.getByRole('button', { name: /Empanadas de pino/ })).toBeVisible()
  const logo = page.locator('main img').first()
  await expect(logo).toBeVisible()

  await context.setOffline(true)
  await page.reload()
  await expect(page.getByText(/Sin conexión: datos guardados/)).toBeVisible()
  await expect(page.getByRole('button', { name: /Empanadas de pino/ })).toBeVisible()
  await expect.poll(() => logo.evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth)).toBeGreaterThan(0)
  await context.setOffline(false)
})

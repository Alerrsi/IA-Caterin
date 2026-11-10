import { expect, test } from '@playwright/test'

const EMAIL = process.env.E2E_EMAIL ?? 'duena.aromos@demo.local'
const PASSWORD = process.env.E2E_PASSWORD ?? 'caterin-demo-2026'
// PNG de 1×1 px: la API de desarrollo no tiene modelo cargado y responde 503, que es el camino que se prueba.
const PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
  'base64',
)

test('foto sin modelo: ofrece registrar a mano y confirma la producción', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Correo').fill(EMAIL)
  await page.getByLabel('Contraseña').fill(PASSWORD)
  await page.getByRole('button', { name: 'Entrar' }).click()
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await page.goto('/#/foto')
  await expect(page.getByRole('heading', { name: 'Contar con foto' })).toBeVisible()

  await page.getByLabel('Elegir foto').setInputFiles({ name: 'bandeja.png', mimeType: 'image/png', buffer: PNG })
  await expect(page.getByText(/no está disponible ahora/)).toBeVisible()
  await page.getByLabel('Producto').selectOption({ label: 'Empanadas de pino' })
  await page.getByLabel('Cantidad').fill('1')
  await page.getByRole('button', { name: 'Confirmar producción' }).click()
  await expect(page.getByText('Producción registrada.')).toBeVisible()
  await expect(page.getByText(/cambio/)).toHaveCount(0, { timeout: 10_000 }) // la cola quedó vacía

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
  expect(overflow).toBeLessThanOrEqual(0)
  await page.screenshot({ path: 'e2e-artifacts/foto-390.png', fullPage: true })
})

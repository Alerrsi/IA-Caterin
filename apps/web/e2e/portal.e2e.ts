import { expect, test } from '@playwright/test'

/**
 * Portal de clientes con navegador (T13, T15): del inicio del cliente al catálogo, elegir productos y guardar la
 * cotización. Usa la pyme de demo grande (`python -m app.db.demo_full`) y uno de sus clientes sintéticos.
 */
const EMAIL = process.env.E2E_CUSTOMER ?? 'cliente1.llaima@demo.local'
const PASSWORD = process.env.E2E_PASSWORD ?? 'caterin-demo-2026'

test('el cliente llega a cotizar en 3 clics y guarda una cotización con productos del catálogo', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Correo').fill(EMAIL)
  await page.getByLabel('Contraseña').fill(PASSWORD)
  await page.getByRole('button', { name: 'Entrar' }).click()
  await expect(page.getByRole('heading', { name: 'Mis cotizaciones' })).toBeVisible()

  // Clic 1: Pymes (barra inferior).
  await page.getByRole('navigation', { name: 'Navegación principal' }).getByRole('link', { name: 'Pymes' }).click()
  await expect(page.getByRole('heading', { name: 'Pymes de catering' })).toBeVisible()
  await page.waitForLoadState('networkidle')
  await page.screenshot({ path: 'e2e-artifacts/pymes-390.png', fullPage: true })
  // Clic 2: la tarjeta de la pyme.
  await page.getByRole('link', { name: /Volcán Llaima/ }).click()
  await expect(page.getByRole('heading', { level: 1, name: /Volcán Llaima/ })).toBeVisible()
  await expect(page.getByRole('heading', { level: 2, name: 'Cóctel' })).toBeVisible()
  // El producto oculto por la dueña no aparece, y no hay precios en el catálogo.
  await expect(page.getByText('Choripanes de cóctel')).toHaveCount(0)
  await expect(page.getByText(/\$\d/)).toHaveCount(0)

  await page.getByRole('button', { name: /Agregar.*Empanadas de pino/ }).click()
  await page.getByRole('button', { name: /Agregar.*Kuchen de murta/ }).click()
  await page.waitForLoadState('networkidle')
  await page.screenshot({ path: 'e2e-artifacts/pyme-productos-390.png' })
  // Clic 3: cotizar.
  await page.getByRole('button', { name: 'Cotizar 2 productos' }).click()
  await expect(page.getByLabel('Producto 1')).toHaveValue(/.+/)
  await expect(page.getByText(/Cotizando con Banquetería Volcán Llaima/)).toBeVisible()

  const qty = page.getByLabel('Cantidad')
  await qty.nth(0).fill('24')
  await qty.nth(1).fill('2')
  await page.getByRole('button', { name: 'Ver precio y guardar' }).click()
  await expect(page.getByRole('heading', { name: 'Tu cotización' })).toBeVisible()
  await expect(page.getByText('Empanadas de pino').first()).toBeVisible()
  await expect(page.getByText('Kuchen de murta').first()).toBeVisible()
})

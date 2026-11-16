import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'

const EMAIL = process.env.E2E_EMAIL ?? 'duena.aromos@demo.local'
const PASSWORD = process.env.E2E_PASSWORD ?? 'caterin-demo-2026'

async function noSeriousAxe(page: Page, name: string) {
  const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze()
  const serious = result.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')
  expect(serious.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`), name).toEqual([])
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
  expect(overflow, `scroll horizontal en ${name}`).toBeLessThanOrEqual(0)
}

/**
 * Registro a mano (no depende de que la API tenga modelo de visión): vista previa de lo que se suma y descuenta,
 * confirmación, existencias en "Productos listos" y anulación para dejar los datos como estaban (T18).
 */
test('producción a mano: vista previa, suma a existencias y se anula', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Correo').fill(EMAIL)
  await page.getByLabel('Contraseña').fill(PASSWORD)
  await page.getByRole('button', { name: 'Entrar' }).click()
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await page.goto('/#/foto')
  await expect(page.getByRole('heading', { name: 'Contar con foto' })).toBeVisible()

  await page.getByRole('button', { name: 'Contar a mano' }).click()
  await page.getByLabel('Producto').selectOption({ label: 'Empanadas de pino' })
  await page.getByLabel('Cantidad').fill('2')
  await expect(page.getByText(/Se suman 2 unid\. de Empanadas de pino/)).toBeVisible()
  await expect(page.getByText(/Se descuentan \d+ insumos?/)).toBeVisible()
  await noSeriousAxe(page, 'foto')
  await page.screenshot({ path: 'e2e-artifacts/foto-390.png', fullPage: true })
  await page.getByRole('button', { name: 'Confirmar producción' }).click()
  await expect(page.getByText('Producción registrada y sumada a tus existencias.')).toBeVisible()
  await expect(page.getByText(/cambio/)).toHaveCount(0, { timeout: 10_000 }) // la cola quedó vacía

  await page.getByRole('button', { name: 'Ver productos listos' }).click()
  const recent = page.getByRole('region', { name: 'Producción reciente' })
  const row = recent.getByRole('listitem').first()
  await expect(row).toContainText('Empanadas de pino')
  await expect(row).toContainText('+2')
  await noSeriousAxe(page, 'productos listos')
  await page.screenshot({ path: 'e2e-artifacts/productos-listos-390.png', fullPage: true })

  await row.getByRole('button', { name: 'Anular' }).click()
  await row.getByRole('button', { name: 'Sí, anular' }).click()
  await expect(page.getByText(/Producción anulada/)).toBeVisible()
  await expect(recent.getByRole('listitem').first()).toContainText('Anulada')
})

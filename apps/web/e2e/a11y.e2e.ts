import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'

const EMAIL = process.env.E2E_EMAIL ?? 'duena.aromos@demo.local'
const PASSWORD = process.env.E2E_PASSWORD ?? 'caterin-demo-2026'

/** axe (WCAG 2.1 A/AA) en cada pantalla clave, a 390 px. Falla si hay violaciones serias o críticas. */
async function audit(page: Page, name: string) {
  const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze()
  const serious = result.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')
  const summary = serious.map((v) => `${v.id} (${v.impact}): ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)
  expect(summary, `axe en ${name}`).toEqual([])
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
  expect(overflow, `scroll horizontal en ${name}`).toBeLessThanOrEqual(0)
}

test('accesibilidad: login y registro', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByLabel('Correo')).toBeVisible()
  await audit(page, 'login')
  await page.goto('/#/registro')
  await expect(page.getByRole('heading', { name: 'Crear cuenta' })).toBeVisible()
  await audit(page, 'registro')
})

test('accesibilidad: pantallas con sesión de dueña', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Correo').fill(EMAIL)
  await page.getByLabel('Contraseña').fill(PASSWORD)
  await page.getByRole('button', { name: 'Entrar' }).click()
  await expect(page.getByRole('heading', { name: /Hola/ })).toBeVisible()
  await expect(page.getByText(/insumo|Ningún insumo/).first()).toBeVisible()
  await audit(page, 'inicio')
  const screens: [string, RegExp][] = [
    ['/inventario', /Inventario/],
    ['/recetas', /Recetas/],
    ['/foto', /Contar con foto/],
    ['/preguntar', /Preguntar/],
    ['/cotizar', /Cotizar un pedido/],
    ['/pedidos', /Mis pedidos/],
    ['/ajustes', /Ajustes/],
    ['/importar', /Importar planilla/],
    ['/metricas', /Mis métricas/],
  ]
  for (const [path, heading] of screens) {
    await page.goto(`/#${path}`)
    await expect(page.getByRole('heading', { level: 1, name: heading })).toBeVisible()
    await page.waitForLoadState('networkidle')
    await audit(page, path)
  }
})

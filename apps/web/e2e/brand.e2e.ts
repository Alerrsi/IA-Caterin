import { expect, test, type Page } from '@playwright/test'

/**
 * Capturas de la identidad visual (T14, T16; estética de T21, ADR-013) a 390 y 1280 px, para comparar antes y después:
 *   SHOTS=antes npx playwright test e2e/brand.e2e.ts   (por defecto: despues)
 * Usa la pyme de demo grande (demo_full): Banquetería Volcán Llaima y su cliente de portal.
 */
const DIR = `e2e-artifacts/${process.env.SHOTS ?? 'despues'}`
const PASSWORD = process.env.E2E_PASSWORD ?? 'caterin-demo-2026'
const WIDTHS = [390, 1280]

async function login(page: Page, email: string) {
  await page.goto('/')
  await page.getByLabel('Correo').fill(email)
  await page.getByLabel('Contraseña').fill(PASSWORD)
  await page.getByRole('button', { name: 'Entrar' }).click()
}

/** Captura la pantalla actual en cada ancho. */
async function shoot(page: Page, name: string) {
  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 800 })
    await page.waitForLoadState('networkidle')
    await expect(page.getByRole('status').filter({ hasText: /^Cargando/ })).toHaveCount(0)
    await page.screenshot({ path: `${DIR}/${name}-${width}.png`, fullPage: true })
  }
  await page.setViewportSize({ width: 390, height: 844 })
}

test('capturas de la identidad visual: login y dueña', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByLabel('Correo')).toBeVisible()
  await shoot(page, 'login')
  await login(page, 'duena.llaima@demo.local')
  await expect(page.getByRole('heading', { name: /Hola/ })).toBeVisible()
  await shoot(page, 'inicio-duena')
  await page.goto('/#/cotizar')
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await shoot(page, 'cotizar')
  await page.goto('/#/pedidos')
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await shoot(page, 'pedidos')
  await page.goto('/#/inventario')
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await shoot(page, 'inventario')
})

test('capturas de la identidad visual: cliente del portal', async ({ page }) => {
  await login(page, 'cliente1.llaima@demo.local')
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await shoot(page, 'inicio-cliente')
  await page.goto('/#/pymes')
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await shoot(page, 'pymes')
  await page.getByRole('link', { name: /Volcán Llaima/ }).first().click()
  await expect(page.getByRole('heading', { level: 1, name: /Volcán Llaima/ })).toBeVisible()
  await shoot(page, 'pyme-productos')
})

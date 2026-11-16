import { expect, test, type Page } from '@playwright/test'

/**
 * Capturas del rediseño T21 (ADR-013) a 390 y 1280 px, para compararlas con la imagen de referencia:
 *   SCREENS=login,inicio npx playwright test e2e/t21.e2e.ts   (por defecto, todas)
 * Usa la demo grande (demo_full): la dueña y el cliente de Banquetería Volcán Llaima. Quedan en e2e-artifacts/t21/.
 */
const DIR = 'e2e-artifacts/t21'
const PASSWORD = process.env.E2E_PASSWORD ?? 'caterin-demo-2026'
const ONLY = process.env.SCREENS?.split(',')
const want = (name: string) => !ONLY || ONLY.includes(name)

async function shoot(page: Page, name: string) {
  for (const width of [390, 1280]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 800 })
    await page.waitForTimeout(250)
    await expect(page.getByRole('status').filter({ hasText: /^Cargando/ })).toHaveCount(0)
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
    expect(overflow, `scroll horizontal en ${name} a ${width} px`).toBeLessThanOrEqual(0)
    await page.screenshot({ path: `${DIR}/${name}-${width}.png` })
    await page.screenshot({ path: `${DIR}/${name}-${width}-completa.png`, fullPage: true })
  }
  await page.setViewportSize({ width: 390, height: 844 })
}

async function login(page: Page, email: string) {
  await page.goto('/')
  await page.getByLabel('Correo').fill(email)
  await page.getByLabel('Contraseña').fill(PASSWORD)
  await page.getByRole('button', { name: 'Entrar' }).click()
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
}

test('capturas T21: dueña', async ({ page }) => {
  test.setTimeout(180_000)
  await page.goto('/')
  await expect(page.getByLabel('Correo')).toBeVisible()
  if (want('login')) await shoot(page, 'login')
  await login(page, 'duena.llaima@demo.local')
  const screens: [string, string][] = [
    ['inicio', '/'],
    ['cotizar', '/cotizar'],
    ['pedidos', '/pedidos'],
    ['inventario', '/inventario'],
    ['productos-listos', '/inventario/productos'],
    ['recetas', '/recetas'],
    ['foto', '/foto'],
    ['preguntar', '/preguntar'],
    ['tablero', '/tablero'],
    ['metricas', '/metricas'],
    ['ajustes', '/ajustes'],
    ['importar', '/importar'],
  ]
  for (const [name, path] of screens) {
    if (!want(name)) continue
    await page.goto(`/#${path}`)
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    await page.waitForLoadState('networkidle')
    await shoot(page, name)
  }
})

test('capturas T21: cliente del portal', async ({ page }) => {
  test.setTimeout(120_000)
  await login(page, 'cliente1.llaima@demo.local')
  if (want('portal-inicio')) await shoot(page, 'portal-inicio')
  await page.goto('/#/pymes')
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  if (want('portal-pymes')) await shoot(page, 'portal-pymes')
  await page.getByRole('link', { name: /Volcán Llaima/ }).first().click()
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await page.waitForLoadState('networkidle')
  if (want('portal-pyme')) await shoot(page, 'portal-pyme')
})

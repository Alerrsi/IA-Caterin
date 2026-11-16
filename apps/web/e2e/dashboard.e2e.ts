import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'

/**
 * Tablero del negocio (T17) con la pyme de demo grande (demo_full: Banquetería Volcán Llaima), a 390 y 1280 px:
 * axe sin violaciones serias, sin scroll horizontal, tooltip al tocar una columna y capturas en e2e-artifacts/tablero.
 */
const EMAIL = process.env.E2E_EMAIL ?? 'duena.llaima@demo.local'
const PASSWORD = process.env.E2E_PASSWORD ?? 'caterin-demo-2026'
const DIR = 'e2e-artifacts/tablero'

async function login(page: Page) {
  await page.goto('/')
  await page.getByLabel('Correo').fill(EMAIL)
  await page.getByLabel('Contraseña').fill(PASSWORD)
  await page.getByRole('button', { name: 'Entrar' }).click()
  await expect(page.getByRole('heading', { name: /Hola/ })).toBeVisible()
}

test('tablero de la dueña: accesible, sin scroll horizontal y con tooltip', async ({ page }) => {
  await login(page)
  await page.getByRole('button', { name: /Mi negocio/ }).click()
  const sales = page.getByRole('region', { name: 'Venta por mes' })
  await expect(sales.getByRole('img').first()).toBeVisible()

  // Vuelve a 390 al final: al girar el teléfono los gráficos deben achicarse, no empujar la página.
  for (const width of [390, 1280, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 800 })
    await page.waitForTimeout(200) // el gráfico se vuelve a dibujar con el ancho nuevo
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
    expect(overflow, `scroll horizontal a ${width} px`).toBeLessThanOrEqual(0)
    const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze()
    const serious = result.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')
    expect(serious.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([])
    if (width === 1280) await page.screenshot({ path: `${DIR}/tablero-${width}.png`, fullPage: true })
  }

  await page.screenshot({ path: `${DIR}/tablero-390.png`, fullPage: true })
  await sales.getByRole('img').last().click()
  await expect(sales.getByText(/pedidos?$/).first()).toBeVisible()
  await page.screenshot({ path: `${DIR}/tablero-tooltip-390.png` })
})

import { expect, test, type Page } from '@playwright/test'

/**
 * Capturas a 390 px de la identidad visual (T14), para comparar antes y después:
 *   SHOTS=antes npx playwright test e2e/brand.e2e.ts   (por defecto: despues)
 * Usa la pyme de demo grande (demo_full): Banquetería Volcán Llaima y su cliente de portal.
 */
const DIR = `e2e-artifacts/${process.env.SHOTS ?? 'despues'}`
const PASSWORD = process.env.E2E_PASSWORD ?? 'caterin-demo-2026'

async function login(page: Page, email: string) {
  await page.goto('/')
  await page.getByLabel('Correo').fill(email)
  await page.getByLabel('Contraseña').fill(PASSWORD)
  await page.getByRole('button', { name: 'Entrar' }).click()
}

test('capturas de la identidad visual: login y dueña', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByLabel('Correo')).toBeVisible()
  await page.screenshot({ path: `${DIR}/login-390.png`, fullPage: true })
  await login(page, 'duena.llaima@demo.local')
  await expect(page.getByRole('heading', { name: /Hola/ })).toBeVisible()
  await page.waitForLoadState('networkidle')
  await page.screenshot({ path: `${DIR}/inicio-duena-390.png`, fullPage: true })
  await page.goto('/#/cotizar')
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await page.screenshot({ path: `${DIR}/cotizar-390.png`, fullPage: true })
})

test('capturas de la identidad visual: cliente del portal', async ({ page }) => {
  await login(page, 'cliente1.llaima@demo.local')
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await page.waitForLoadState('networkidle')
  await page.screenshot({ path: `${DIR}/inicio-cliente-390.png`, fullPage: true })
})

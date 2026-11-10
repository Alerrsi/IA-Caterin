import { expect, test, type Locator } from '@playwright/test'

const EMAIL = process.env.E2E_EMAIL ?? 'duena.aromos@demo.local'
const PASSWORD = process.env.E2E_PASSWORD ?? 'caterin-demo-2026'

/** "3 kg" -> 3, "2,5 kg" -> 2.5 */
async function kg(row: Locator): Promise<number> {
  const text = (await row.getByText(/^-?[\d.,]+ kg$/).textContent()) ?? ''
  return Number(text.replace(' kg', '').replace(/\./g, '').replace(',', '.'))
}

test('inventario: sumar con señal, restar sin señal y sincronizar al volver', async ({ page, context }) => {
  await page.goto('/')
  await page.getByLabel('Correo').fill(EMAIL)
  await page.getByLabel('Contraseña').fill(PASSWORD)
  await page.getByRole('button', { name: 'Entrar' }).click()
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await page.goto('/#/inventario')

  await page.getByLabel('Buscar insumo').fill('Sal')
  const row = page.locator('li', { has: page.getByText('Sal', { exact: true }) })
  await expect(row).toHaveCount(1)
  const before = await kg(row)

  // Con señal: +1 kg (compra)
  await row.getByRole('button', { name: 'Sumar a Sal' }).click()
  await row.getByLabel('Cantidad').fill('1')
  await row.getByRole('button', { name: 'Guardar' }).click()
  await expect.poll(() => kg(row)).toBe(before + 1)
  await expect(page.getByText(/cambios? por enviar|Enviando/)).toHaveCount(0)

  // Sin señal: −1 kg (ajuste) queda en la cola
  await context.setOffline(true)
  await row.getByRole('button', { name: 'Restar a Sal' }).click()
  await row.getByLabel('Cantidad').fill('1')
  await row.getByLabel('Motivo').selectOption('adjustment')
  await row.getByRole('button', { name: 'Guardar' }).click()
  await expect(page.getByText('1 cambio por enviar')).toBeVisible()
  await expect(row.getByText('Por enviar')).toBeVisible()
  await expect.poll(() => kg(row)).toBe(before)

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
  expect(overflow).toBeLessThanOrEqual(0)
  await page.screenshot({ path: 'e2e-artifacts/inventario-390.png', fullPage: true })

  // Vuelve la señal: se envía sola y el servidor queda como al principio
  await context.setOffline(false)
  await expect(page.getByText(/cambios? por enviar|Enviando/)).toHaveCount(0, { timeout: 15_000 })
  await expect(row.getByText('Por enviar')).toHaveCount(0)
  await page.reload()
  await page.getByLabel('Buscar insumo').fill('Sal')
  await expect.poll(() => kg(row)).toBe(before)
})

import { expect, test } from '@playwright/test'

const EMAIL = process.env.E2E_EMAIL ?? 'duena.aromos@demo.local'
const PASSWORD = process.env.E2E_PASSWORD ?? 'caterin-demo-2026'

test('asistente: botón rápido, pregunta escrita con fuente, opciones y feedback', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Correo').fill(EMAIL)
  await page.getByLabel('Contraseña').fill(PASSWORD)
  await page.getByRole('button', { name: 'Entrar' }).click()
  await page.getByRole('button', { name: /Preguntar/ }).click()
  await expect(page).toHaveURL(/#\/preguntar/)

  await page.getByRole('button', { name: 'Pedidos de esta semana' }).click()
  await expect(page.getByText(/Fuente: tus pedidos/).first()).toBeVisible()

  await page.getByLabel('Tu pregunta').fill('¿Qué lleva el pedido del matrimonio?')
  await page.getByRole('button', { name: 'Preguntar', exact: true }).click()
  await expect(page.getByText(/20 docenas de Empanadas de queso/)).toBeVisible()

  await page.getByLabel('Tu pregunta').fill('¿Cuánta crema me queda?')
  await page.getByRole('button', { name: 'Preguntar', exact: true }).click()
  await page.getByRole('button', { name: 'Crema de leche' }).click()
  await expect(page.getByText(/de Crema de leche\./)).toBeVisible()

  await page.getByRole('button', { name: 'Me sirvió' }).last().click()
  await expect(page.getByText(/Gracias, lo usaremos/)).toBeVisible()
  // Sin scroll horizontal en 390 px (mobile-first)
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
  expect(overflow).toBeLessThanOrEqual(0)
  await page.screenshot({ path: 'e2e-artifacts/asistente-390.png', fullPage: true })
})

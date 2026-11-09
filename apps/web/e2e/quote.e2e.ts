import { expect, test } from '@playwright/test'

const EMAIL = process.env.E2E_EMAIL ?? 'duena.aromos@demo.local'
const PASSWORD = process.env.E2E_PASSWORD ?? 'caterin-demo-2026'

test('login, pedido a mano de 24 sopaipillas, cotización y PDF', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Correo').fill(EMAIL)
  await page.getByLabel('Contraseña').fill(PASSWORD)
  await page.getByRole('button', { name: 'Entrar' }).click()

  await page.getByRole('button', { name: /Cotizar un pedido/ }).click()
  await page.getByRole('button', { name: 'Ingresar a mano' }).click()
  await page.getByLabel('Nombre del cliente').fill('Cliente E2E (demo)')
  await page.getByLabel('Invitados').fill('20')
  await page.getByLabel('Receta 1').selectOption({ label: 'Sopaipillas' })
  await page.getByLabel('Cantidad').fill('24')
  await page.getByRole('button', { name: 'Calcular cotización' }).click()

  await expect(page).toHaveURL(/#\/cotizaciones\//)
  const total = page.getByTestId('quote-total')
  await expect(total).toHaveText(/^\$\d{1,3}(\.\d{3})*$/)
  await expect(page.getByText('Sopaipillas')).toBeVisible()
  await page.screenshot({ path: 'e2e-artifacts/cotizacion-390.png', fullPage: true })

  await page.locator('summary', { hasText: 'Lista de compras' }).click()
  await expect(page.getByText('Total compras')).toBeVisible()
  await page.screenshot({ path: 'e2e-artifacts/lista-compras-390.png', fullPage: true })

  // El PDF responde 200 con el mismo token que usa la app
  const quoteId = page.url().split('/').pop()
  const status = await page.evaluate(async (id) => {
    const r = await fetch('/api/v1/auth/refresh', { method: 'POST', credentials: 'include' })
    const { access_token } = await r.json()
    const pdf = await fetch(`/api/v1/quotes/${id}/pdf`, { headers: { Authorization: `Bearer ${access_token}` } })
    return { status: pdf.status, type: pdf.headers.get('content-type') }
  }, quoteId)
  expect(status).toEqual({ status: 200, type: 'application/pdf' })
})

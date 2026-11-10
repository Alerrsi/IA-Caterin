import { expect, test, type Page } from '@playwright/test'

const EMAIL = process.env.E2E_EMAIL ?? 'duena.aromos@demo.local'
const PASSWORD = process.env.E2E_PASSWORD ?? 'caterin-demo-2026'

async function noHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
  expect(overflow).toBeLessThanOrEqual(0)
}

test('ajustes e importar insumos (cargar y deshacer)', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Correo').fill(EMAIL)
  await page.getByLabel('Contraseña').fill(PASSWORD)
  await page.getByRole('button', { name: 'Entrar' }).click()
  await expect(page.getByRole('heading', { name: /^Hola/ })).toBeVisible()

  await page.goto('/#/ajustes')
  await expect(page.getByLabel(/^Margen de ganancia/)).toHaveValue(/\d/)
  await expect(page.getByText('colaboradora.aromos@demo.local')).toBeVisible()
  await noHorizontalScroll(page)
  await page.screenshot({ path: 'e2e-artifacts/ajustes-390.png', fullPage: true })

  await page.goto('/#/importar')
  const name = `Insumo E2E ${Date.now()}`
  const csv = `nombre;unidad;stock;stock_minimo;merma_pct;categoria\n${name};kg;2;1;;Pruebas E2E\nInsumo con error;sacos;1;;;\n`
  await page.getByLabel(/Planilla/).setInputFiles({ name: 'insumos.csv', mimeType: 'text/csv', buffer: Buffer.from(csv) })
  await page.getByRole('button', { name: 'Revisar planilla' }).click()
  await expect(page.getByText('1 de 2 filas están bien.')).toBeVisible()
  await expect(page.getByText(name)).toBeVisible()
  await expect(page.getByText(/Fila 3 ·/)).toBeVisible()
  await page.getByRole('button', { name: 'Cargar 1 fila' }).click()
  await expect(page.getByText('Se cargó 1 fila.')).toBeVisible()
  await noHorizontalScroll(page)
  await page.screenshot({ path: 'e2e-artifacts/importar-390.png', fullPage: true })

  await page.getByRole('button', { name: 'Deshacer esta carga' }).click()
  await expect(page.getByText('Carga deshecha.')).toBeVisible()

  // El insumo ya no existe: la base de desarrollo queda como estaba
  const found = await page.evaluate(async (n) => {
    const r = await fetch('/api/v1/auth/refresh', { method: 'POST', credentials: 'include' })
    const { access_token } = await r.json()
    const list = await fetch(`/api/v1/ingredients?q=${encodeURIComponent(n)}`, {
      headers: { Authorization: `Bearer ${access_token}` },
    })
    return (await list.json()).items.length
  }, name)
  expect(found).toBe(0)
})

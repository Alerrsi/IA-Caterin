import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Locator, type Page } from '@playwright/test'
import { mkdirSync, writeFileSync } from 'node:fs'

/**
 * Criterio global del MVP (AGENTS.md, sección 9): una usuaria NUEVA carga insumos y una receta y obtiene su
 * primera cotización con PDF, solo con la interfaz. Mide toques, campos escritos, pantallas y tiempo.
 * Crea una pyme de prueba nueva en la base de desarrollo en cada corrida (correo único).
 */

const stats = { taps: 0, fields: 0, screens: new Set<string>() }

async function tap(target: Locator) {
  stats.taps += 1
  await target.click()
}
async function choose(target: Locator, value: string | { label: string }) {
  stats.taps += 1
  await target.selectOption(value)
}
async function write(target: Locator, text: string) {
  stats.fields += 1
  await target.fill(text)
}

async function audit(page: Page, name: string) {
  const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze()
  const serious = result.violations
    .filter((v) => v.impact === 'serious' || v.impact === 'critical')
    .map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)
  expect(serious, `axe en ${name}`).toEqual([])
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
  expect(overflow, `scroll horizontal en ${name}`).toBeLessThanOrEqual(0)
}

test('MVP: usuaria nueva → insumos → precios → receta → cotización con PDF', async ({ page }) => {
  test.setTimeout(120_000)
  page.on('framenavigated', (f) => {
    if (f === page.mainFrame()) stats.screens.add(new URL(f.url()).hash.replace(/\/[0-9a-f-]{36}$/, '/:id') || '#/')
  })
  const start = Date.now()
  const stamp = Date.now()

  // 1. Registro (con el margen, opcional, para poder cotizar)
  await page.goto('/#/registro')
  await write(page.getByLabel('Nombre de tu pyme'), `Pyme E2E ${stamp} (prueba)`)
  await write(page.getByLabel('Tu nombre'), 'Usuaria Prueba')
  await write(page.getByLabel('Correo'), `mvp-${stamp}@demo.local`)
  await write(page.getByLabel(/^Contraseña/), 'clave-segura-e2e-mvp')
  await write(page.getByLabel(/^Margen de ganancia/), '40')
  await audit(page, 'registro')
  await tap(page.getByRole('button', { name: 'Crear cuenta' }))
  await expect(page.getByRole('heading', { name: 'Hola, Usuaria' })).toBeVisible()

  // 2. Insumos con "Nuevo insumo": al guardar se abre su detalle, donde se agrega el precio
  await tap(page.getByRole('button', { name: /^Inventario/ }))
  await tap(page.getByRole('button', { name: 'Nuevo insumo' }))
  await write(page.getByLabel('Nombre del insumo'), 'Harina sin polvos')
  await write(page.getByLabel('Cuánto tienes ahora'), '10') // en kg (por defecto)
  await audit(page, 'nuevo insumo')
  await page.screenshot({ path: 'e2e-artifacts/nuevo-insumo-390.png', fullPage: true })
  await tap(page.getByRole('button', { name: 'Guardar insumo' }))
  await expect(page.getByRole('heading', { name: 'Harina sin polvos' })).toBeVisible()
  await expect(page.getByText(/Todavía no tiene precio/)).toBeVisible()
  await audit(page, 'detalle de insumo')
  await tap(page.getByRole('button', { name: 'Agregar precio' }))
  await write(page.getByLabel('Nombre del proveedor nuevo'), 'Proveedor E2E')
  await write(page.getByLabel('Presentación'), 'saco 25 kg')
  await write(page.getByLabel('Cantidad que trae'), '25')
  await write(page.getByLabel('Precio en pesos'), '21.000')
  await audit(page, 'formulario de precio')
  await tap(page.getByRole('button', { name: 'Guardar precio' }))
  await expect(page.getByText('Precio guardado.')).toBeVisible()

  await tap(page.getByRole('button', { name: 'Volver' }))
  await tap(page.getByRole('button', { name: 'Nuevo insumo' }))
  await write(page.getByLabel('Nombre del insumo'), 'Huevo')
  await tap(page.getByLabel('Por unidad'))
  await write(page.getByLabel('Cuánto tienes ahora'), '30')
  await tap(page.getByRole('button', { name: 'Guardar insumo' }))
  await expect(page.getByRole('heading', { name: 'Huevo' })).toBeVisible()
  await tap(page.getByRole('button', { name: 'Agregar precio' }))
  await choose(page.getByLabel('Proveedor'), { label: 'Proveedor E2E' })
  await write(page.getByLabel('Presentación'), 'bandeja 30')
  await write(page.getByLabel('Cantidad que trae'), '30')
  await write(page.getByLabel('Precio en pesos'), '6.000')
  await tap(page.getByRole('button', { name: 'Guardar precio' }))
  await expect(page.getByText('Precio guardado.')).toBeVisible()
  await page.screenshot({ path: 'e2e-artifacts/precio-390.png', fullPage: true })
  await tap(page.getByRole('button', { name: 'Volver' }))
  await expect(page.getByRole('heading', { name: 'Inventario' })).toBeVisible()
  await audit(page, 'inventario')
  await tap(page.getByRole('button', { name: 'Volver' }))

  // 5. Receta
  await tap(page.getByRole('button', { name: 'Recetas' }))
  await tap(page.getByRole('button', { name: 'Nueva receta' }))
  await write(page.getByLabel('Nombre de la receta'), 'Sopaipillas E2E')
  await write(page.getByLabel('Rinde (cantidad)'), '12')
  const l1 = page.getByRole('group', { name: 'Insumo 1' })
  await choose(l1.getByRole('combobox', { name: 'Insumo', exact: true }), { label: 'Harina sin polvos' })
  await write(l1.getByRole('textbox', { name: 'Cantidad' }), '0,5')
  await tap(page.getByRole('button', { name: 'Agregar otro insumo' }))
  const l2 = page.getByRole('group', { name: 'Insumo 2' })
  await choose(l2.getByRole('combobox', { name: 'Insumo', exact: true }), { label: 'Huevo' })
  await write(l2.getByRole('textbox', { name: 'Cantidad' }), '2')
  await audit(page, 'nueva receta')
  await page.screenshot({ path: 'e2e-artifacts/nueva-receta-390.png', fullPage: true })
  await tap(page.getByRole('button', { name: 'Guardar receta' }))
  await expect(page.getByRole('heading', { name: 'Sopaipillas E2E' })).toBeVisible()
  await expect(page.getByText('Harina sin polvos').first()).toBeVisible()
  await tap(page.getByRole('button', { name: 'Volver' }))
  await tap(page.getByRole('button', { name: 'Volver' }))

  // 6. Cotización con un pedido ingresado a mano (sin LLM) y su PDF
  await tap(page.getByRole('button', { name: /Cotizar un pedido/ }))
  await tap(page.getByRole('button', { name: 'Ingresar a mano' }))
  await write(page.getByLabel('Nombre del cliente'), 'Cliente E2E MVP (prueba)')
  await write(page.getByLabel('Invitados'), '20')
  await choose(page.getByLabel('Receta 1'), { label: 'Sopaipillas E2E' })
  await write(page.getByLabel('Cantidad'), '24')
  await tap(page.getByRole('button', { name: 'Calcular cotización' }))
  await expect(page).toHaveURL(/#\/cotizaciones\//)
  await expect(page.getByTestId('quote-total')).toHaveText(/^\$\d{1,3}(\.\d{3})*$/)
  await expect(page.getByText(/Esta cotización está incompleta/)).toHaveCount(0)
  stats.taps += 1 // "Ver PDF"
  const quoteId = page.url().split('/').pop()
  const pdf = await page.evaluate(async (id) => {
    const r = await fetch('/api/v1/auth/refresh', { method: 'POST', credentials: 'include' })
    const { access_token } = await r.json()
    const res = await fetch(`/api/v1/quotes/${id}/pdf`, { headers: { Authorization: `Bearer ${access_token}` } })
    return { status: res.status, type: res.headers.get('content-type'), size: (await res.arrayBuffer()).byteLength }
  }, quoteId)
  expect(pdf.status).toBe(200)
  expect(pdf.type).toBe('application/pdf')
  await page.screenshot({ path: 'e2e-artifacts/mvp-cotizacion-390.png', fullPage: true })

  const seconds = Math.round((Date.now() - start) / 100) / 10
  const report = {
    measured_at: new Date().toISOString(),
    note: 'Ejecución automática (Playwright): mide toques y pantallas del flujo, NO el tiempo de una persona.',
    taps: stats.taps,
    typed_fields: stats.fields,
    screens: [...stats.screens],
    automated_seconds: seconds,
    pdf_bytes: pdf.size,
  }
  mkdirSync('e2e-artifacts', { recursive: true })
  writeFileSync('e2e-artifacts/mvp-flow.json', JSON.stringify(report, null, 2))
  console.log(JSON.stringify(report))
})

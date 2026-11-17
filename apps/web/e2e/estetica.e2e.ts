import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'

/** Estética de la referencia (T21, ADR-013): barra superior en escritorio, píldoras, atajos, movimiento reducido y fuente. */
const EMAIL = process.env.E2E_EMAIL ?? 'duena.aromos@demo.local'
const PASSWORD = process.env.E2E_PASSWORD ?? 'caterin-demo-2026'

async function login(page: Page) {
  await page.goto('/')
  await page.getByLabel('Correo').fill(EMAIL)
  await page.getByLabel('Contraseña').fill(PASSWORD)
  await page.getByRole('button', { name: 'Entrar' }).click()
  await expect(page.getByRole('heading', { name: /Hola/ })).toBeVisible()
}

test.describe('escritorio', () => {
  test.use({ viewport: { width: 1280, height: 800 }, hasTouch: false, isMobile: false })

  test('atajo C para cotizar, barra superior con píldoras, portada con panel oscuro y sin violaciones de axe', async ({ page }) => {
    await login(page)
    // La barra superior muestra la tecla y el enlace la anuncia.
    const quote = page.getByRole('navigation', { name: 'Secciones' }).getByRole('link', { name: 'Cotizar' })
    await expect(quote).toHaveAttribute('aria-keyshortcuts', 'C')
    await expect(quote.locator('kbd')).toBeVisible()
    // Botones en píldora y la portada del inicio con el panel oscuro.
    const cta = page.getByRole('button', { name: 'Cotizar un pedido' })
    expect(parseFloat(await cta.evaluate((el) => getComputedStyle(el).borderTopLeftRadius))).toBeGreaterThan(100)
    expect(await page.locator('.doodles').first().evaluate((el) => getComputedStyle(el).backgroundColor)).toBe('rgb(27, 27, 27)')
    const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze()
    const serious = result.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')
    expect(serious.map((v) => v.id)).toEqual([])
    await page.keyboard.press('c')
    await expect(page).toHaveURL(/#\/cotizar/)
    // "/" lleva al buscador y, ya dentro del campo, la "c" se escribe y no navega.
    await page.goto('/#/inventario')
    await page.keyboard.press('/')
    await expect(page.getByLabel('Buscar insumo')).toBeFocused()
    await page.keyboard.type('c')
    await expect(page).toHaveURL(/#\/inventario/)
  })
})

test('con "reducir movimiento" la hoja "Más" del celular aparece sin animación (T22)', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await login(page)
  await page.getByRole('navigation', { name: 'Navegación principal' }).getByRole('button', { name: 'Más' }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  expect(await dialog.evaluate((el) => getComputedStyle(el).transitionProperty)).toBe('none')
})

test('la fuente Urbanist carga en sus dos pesos de título', async ({ page }) => {
  await login(page)
  // Pide cada peso: si el archivo no existe o no se puede leer, no queda ninguna cara cargada.
  const faces = ['400 16px "Urbanist Variable"', '800 16px "Urbanist Variable"']
  const loaded = await page.evaluate(
    async (list) => Promise.all(list.map(async (f) => (await document.fonts.load(f)).length > 0)),
    faces,
  )
  expect(loaded).toEqual([true, true])
})

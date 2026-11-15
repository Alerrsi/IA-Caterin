import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'

/** Estética "plano de cocina" (T16, ADR-010): escritorio, atajos, movimiento reducido y fuentes. */
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

  test('atajo C para cotizar, rieles del marco y sin violaciones de axe', async ({ page }) => {
    await login(page)
    // El cajón muestra la tecla y el enlace la anuncia.
    const quote = page.getByRole('navigation', { name: 'Secciones' }).getByRole('link', { name: 'Cotizar' })
    await expect(quote).toHaveAttribute('aria-keyshortcuts', 'C')
    await expect(quote.locator('kbd')).toBeVisible()
    // Los rieles: la pantalla tiene una línea a cada lado.
    const main = page.locator('main').first()
    expect(await main.evaluate((el) => getComputedStyle(el).borderLeftWidth)).toBe('1px')
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

test('con "reducir movimiento" el cajón del celular aparece sin animación', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await login(page)
  await page.getByRole('button', { name: 'Abrir menú' }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  expect(await dialog.evaluate((el) => getComputedStyle(el).transitionProperty)).toBe('none')
})

test('las fuentes IBM Plex cargan', async ({ page }) => {
  await login(page)
  // Pide cada fuente: si el archivo no existe o no se puede leer, no queda ninguna cara cargada.
  const faces = ['500 16px "IBM Plex Serif"', 'italic 16px "IBM Plex Serif"', '16px "IBM Plex Mono"', '600 16px "IBM Plex Sans Variable"']
  const loaded = await page.evaluate(
    async (list) => Promise.all(list.map(async (f) => (await document.fonts.load(f)).length > 0)),
    faces,
  )
  expect(loaded).toEqual([true, true, true, true])
})

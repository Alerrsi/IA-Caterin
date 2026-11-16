import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'
import path from 'node:path'

/**
 * Portada de la pyme en el portal (T19, ADR-012) con la demo grande (Banquetería Volcán Llaima), a 390 y 1280 px:
 * axe sin violaciones serias, sin scroll horizontal y capturas en e2e-artifacts/portada. La demo no tiene fotos de
 * productos; la segunda pasada inyecta fotos de prueba en la respuesta del catálogo (no toca la base).
 */
const EMAIL = process.env.E2E_CUSTOMER_EMAIL ?? 'cliente1.llaima@demo.local'
const PASSWORD = process.env.E2E_PASSWORD ?? 'caterin-demo-2026'
const DIR = 'e2e-artifacts/portada'
const PHOTOS = path.resolve(import.meta.dirname, '../../../ml/vision/fotos-prueba')

async function openPyme(page: Page) {
  await page.goto('/')
  await page.getByLabel('Correo').fill(EMAIL)
  await page.getByLabel('Contraseña').fill(PASSWORD)
  await page.getByRole('button', { name: 'Entrar' }).click()
  await expect(page.getByRole('heading', { name: 'Mis cotizaciones' })).toBeVisible()
  await page.goto('/#/pymes')
  await page.getByRole('link', { name: /Volcán Llaima/ }).click()
  await expect(page.getByRole('heading', { level: 1, name: /Volcán Llaima/ })).toBeVisible()
}

async function check(page: Page, name: string) {
  for (const width of [390, 1280]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 })
    await page.waitForLoadState('networkidle')
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
    expect(overflow, `scroll horizontal a ${width} px`).toBeLessThanOrEqual(0)
    const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze()
    const serious = result.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')
    expect(serious.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([])
    await page.screenshot({ path: `${DIR}/${name}-${width}.png` })
    await page.screenshot({ path: `${DIR}/${name}-${width}-completa.png`, fullPage: true })
  }
}

test('portada de la pyme: demo sin fotos', async ({ page }) => {
  await openPyme(page)
  // Sin fotos, el destacado es el primero con descripción en el orden del catálogo (Cóctel: Brochetas caprese).
  const hero = page.getByRole('region', { name: 'Brochetas caprese' })
  await expect(hero).toBeVisible()
  await expect(hero.getByRole('article', { name: 'Canapés de queso de cabra y murta' })).toBeVisible()
  await expect(hero.getByText('Precio al cotizar')).toBeVisible()
  await expect(page.getByText(/\$/)).toHaveCount(0)
  await check(page, 'sin-fotos')
})

test('portada de la pyme: con fotos de prueba', async ({ page }) => {
  await page.route('**/api/v1/portal/products*', async (route) => {
    const resp = await route.fetch()
    const items = (await resp.json()) as { name: string; photo_url: string | null }[]
    const files = ['02_empanadas_muchas.jpg', '03_canapes.jpg', '04_brochetas.jpg']
    const withPhotos = items.map((p) => {
      const i = /^Empanadas de pino/.test(p.name) ? 0 : /^Canapés de ave/.test(p.name) ? 1 : /^Brochetas caprese/.test(p.name) ? 2 : -1
      return i >= 0 ? { ...p, photo_url: `/__t19/${files[i]}` } : p
    })
    await route.fulfill({ response: resp, json: withPhotos, headers: { ...resp.headers(), etag: '' } })
  })
  await page.route('**/__t19/*', (route) =>
    route.fulfill({ path: path.join(PHOTOS, path.basename(new URL(route.request().url()).pathname)) }),
  )
  await openPyme(page)
  const hero = page.getByRole('region', { name: 'Brochetas caprese' })
  await expect(hero.locator('img').first()).toBeVisible()
  // Solo las de la portada: las de la grilla cargan perezosas al bajar.
  await expect
    .poll(() => hero.locator('img').evaluateAll((imgs) => imgs.every((i) => (i as HTMLImageElement).naturalWidth > 0)))
    .toBe(true)
  await expect(hero.getByRole('article', { name: 'Canapés de ave palta' })).toBeVisible()
  await check(page, 'con-fotos')
})

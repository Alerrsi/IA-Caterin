import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'

/**
 * T22 — acceso rápido. Con la pyme de demo grande (Banquetería Volcán Llaima):
 * - "mapa de alcance": desde 5 pantallas, a 390 px, cada destino en ≤ 2 toques (se cuentan), y las acciones
 *   principales en ≤ 3;
 * - solo teclado en escritorio: Ctrl+K "harina" → insumo → sumar 1 kg → restar 1 kg (deja la demo igual) → volver;
 * - axe sin violaciones serias en todas las pantallas con la navegación nueva; capturas en e2e-artifacts/t22/.
 */
const OWNER = process.env.E2E_EMAIL ?? 'duena.llaima@demo.local'
const PASSWORD = process.env.E2E_PASSWORD ?? 'caterin-demo-2026'
const DIR = 'e2e-artifacts/t22'

async function login(page: Page) {
  await page.goto('/')
  await page.getByLabel('Correo').fill(OWNER)
  await page.getByLabel('Contraseña').fill(PASSWORD)
  await page.getByRole('button', { name: 'Entrar' }).click()
  // El login también tiene un h1 ("Cáterin"): se espera algo que solo existe con sesión.
  await expect(page.getByRole('button', { name: 'Saltar al contenido' })).toBeAttached()
  await expect(page.getByRole('heading', { level: 1, name: /Hola/ })).toBeVisible()
}

async function audit(page: Page, name: string) {
  const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze()
  const serious = result.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')
  expect(serious.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`), `axe en ${name}`).toEqual([])
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
  expect(overflow, `scroll horizontal en ${name}`).toBeLessThanOrEqual(0)
}

/** Destinos de la dueña: nombre accesible y la ruta a la que debe llegar. */
const DESTINATIONS: [string, RegExp][] = [
  ['Inicio', /#\/$/],
  ['Cotizar', /#\/cotizar$/],
  ['Contar con foto', /#\/foto$/],
  ['Inventario', /#\/inventario$/],
  ['Pedidos', /#\/pedidos$/],
  ['Preguntar', /#\/preguntar$/],
  ['Mi negocio', /#\/tablero$/],
  ['Recetas', /#\/recetas$/],
  ['Productos listos', /#\/inventario\/productos$/],
  ['Importar', /#\/importar$/],
  ['Métricas', /#\/metricas$/],
  ['Ajustes', /#\/ajustes$/],
]

/** Llega a un destino como lo haría la usuaria en el celular y devuelve cuántos toques costó. */
async function reach(page: Page, name: string): Promise<number> {
  const bar = page.getByRole('navigation', { name: 'Navegación principal' })
  const direct = bar.getByRole('link', { name, exact: true })
  if ((await direct.count()) > 0) {
    await direct.click()
    return 1
  }
  await bar.getByRole('button', { name: 'Más' }).click()
  const sheet = page.getByRole('dialog', { name: 'Todo Cáterin' })
  await sheet.getByRole('link', { name, exact: true }).click()
  await expect(sheet).toBeHidden()
  return 2
}

test('mapa de alcance: cada destino a 2 toques o menos desde 5 pantallas (390 px)', async ({ page }) => {
  test.setTimeout(240_000)
  await page.setViewportSize({ width: 390, height: 844 })
  await login(page)
  const table: Record<string, number> = {}
  for (const start of ['/', '/inventario', '/recetas', '/pedidos', '/tablero']) {
    for (const [name, url] of DESTINATIONS) {
      await page.goto(`/#${start}`)
      await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible()
      const taps = await reach(page, name)
      await expect(page, `${name} desde ${start}`).toHaveURL(url)
      expect(taps, `${name} desde ${start}`).toBeLessThanOrEqual(2)
      table[name] = Math.max(table[name] ?? 0, taps)
    }
  }
  console.log('Toques por destino (peor caso):', JSON.stringify(table))
})

test('acciones principales en 3 toques o menos desde el inicio (390 px)', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await login(page)
  const quick = page.getByRole('region', { name: 'Acciones rápidas' })

  // Cotizar: 1 toque y ya se puede pegar el pedido.
  await quick.getByRole('link', { name: 'Cotizar un pedido' }).click()
  await expect(page.getByLabel('Pega aquí el mensaje de tu cliente')).toBeVisible()

  // Contar con foto: 1 toque.
  await page.goto('/#/')
  await quick.getByRole('link', { name: 'Contar con foto' }).click()
  await expect(page.getByRole('heading', { name: 'Contar con foto' })).toBeVisible()

  // Ajustar stock: 1 toque abre el inventario con el buscador listo; 2.º toque abre el ajuste del insumo.
  await page.goto('/#/')
  await quick.getByRole('link', { name: 'Ajustar stock' }).click()
  await expect(page.getByLabel('Buscar insumo')).toBeFocused()
  await page.getByLabel('Buscar insumo').fill('harina')
  await page.getByRole('button', { name: /^Sumar a Harina/ }).first().click()
  await expect(page.getByLabel('Cantidad')).toBeVisible()

  // Ver un pedido: el aviso de solicitudes (1) abre la lista filtrada; "Ver cotización" (2).
  await page.goto('/#/')
  const alert = page.getByRole('button', { name: /solicitud/ })
  if ((await alert.count()) > 0) {
    await alert.first().click()
    await expect(page.getByText('Mostrando solo las solicitudes por responder.')).toBeVisible()
  } else {
    await page.getByRole('navigation', { name: 'Navegación principal' }).getByRole('button', { name: 'Más' }).click()
    await page.getByRole('dialog').getByRole('link', { name: 'Pedidos', exact: true }).click()
  }
  await page.getByRole('button', { name: 'Ver cotización' }).first().click()
  await expect(page).toHaveURL(/#\/cotizaciones\//)
})

test.describe('escritorio', () => {
  test.use({ viewport: { width: 1280, height: 800 }, hasTouch: false, isMobile: false })

  test('solo teclado: Ctrl+K "harina", ajustar el stock y volver', async ({ page }) => {
    await login(page)
    // Al llegar a una pantalla, "Saltar al contenido" es lo primero con Tab.
    await page.evaluate(() => {
      document.body.setAttribute('tabindex', '-1')
      document.body.focus()
      document.body.removeAttribute('tabindex')
    })
    await page.keyboard.press('Tab')
    await expect(page.getByRole('button', { name: 'Saltar al contenido' })).toBeFocused()

    await page.keyboard.press('Control+k')
    const box = page.getByRole('combobox', { name: 'Buscar en Cáterin' })
    await expect(box).toBeFocused()
    await page.keyboard.type('harina')
    await expect(page.getByRole('option', { name: /Harina/ }).first()).toHaveAttribute('aria-selected', 'true')
    await page.screenshot({ path: `${DIR}/buscador-1280.png` })
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/#\/inventario\/[0-9a-f-]+$/)
    const title = page.getByRole('heading', { level: 1 })
    await expect(title).toBeFocused() // el foco va al título de la pantalla nueva
    await expect(title).toHaveText(/Harina/i) // el nombre llega con los datos guardados
    const name = (await title.textContent())?.trim() ?? ''

    // Tab hasta "Sumar a …", Enter, cantidad 1 (kg por defecto) y Enter para guardar.
    for (const [sign, label] of [
      ['Sumar', `Sumar a ${name}`],
      ['Restar', `Restar a ${name}`],
    ]) {
      for (let i = 0; i < 40; i++) {
        await page.keyboard.press('Tab')
        if ((await page.evaluate(() => document.activeElement?.getAttribute('aria-label'))) === label) break
      }
      await expect(page.getByRole('button', { name: label }), sign).toBeFocused()
      await page.keyboard.press('Enter')
      await expect(page.getByLabel('Cantidad')).toBeFocused()
      await page.keyboard.type('1')
      await page.keyboard.press('Enter')
      await expect(page.getByLabel('Cantidad')).toBeHidden()
    }

    // Volver con el teclado: regresa a donde estaba (el inicio), no a un lugar fijo.
    const back = page.getByRole('button', { name: 'Volver' })
    for (let i = 0; i < 40; i++) {
      await page.keyboard.press('Shift+Tab')
      if (await back.evaluate((el) => el === document.activeElement)) break
    }
    await expect(back).toBeFocused()
    await page.keyboard.press('Enter')
    await expect(page.getByRole('heading', { level: 1, name: /Hola/ })).toBeVisible() // el inicio, de donde se vino

    // "?" muestra la ayuda de atajos; Esc la cierra.
    await page.keyboard.press('?')
    await expect(page.getByRole('dialog', { name: 'Atajos de teclado' })).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(page.getByRole('dialog')).toBeHidden()
    await page.keyboard.press('f')
    await expect(page).toHaveURL(/#\/foto$/)
  })
})

test('axe y capturas de la navegación nueva en todas las pantallas (390 y 1280 px)', async ({ page }) => {
  test.setTimeout(240_000)
  await login(page)
  const screens = ['/', '/cotizar', '/foto', '/inventario', '/inventario/productos', '/pedidos', '/preguntar', '/recetas', '/tablero', '/importar', '/metricas', '/ajustes']
  for (const width of [390, 1280]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 800 })
    for (const s of screens) {
      await page.goto(`/#${s}`)
      await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible()
      await page.waitForLoadState('networkidle')
      await audit(page, `${s} a ${width}`)
    }
  }
  // Capturas: inicio, hoja "Más" y buscador.
  for (const width of [390, 1280]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 800 })
    await page.goto('/#/')
    await expect(page.getByRole('region', { name: 'Acciones rápidas' })).toBeVisible()
    await page.screenshot({ path: `${DIR}/inicio-${width}.png`, fullPage: true })
    if (width === 390) await page.getByRole('navigation', { name: 'Navegación principal' }).getByRole('button', { name: 'Más' }).click()
    else await page.getByRole('navigation', { name: 'Secciones' }).getByRole('button', { name: 'Más' }).click()
    const sheet = page.getByRole('dialog', { name: 'Todo Cáterin' })
    await expect(sheet).toBeVisible()
    await audit(page, `hoja Más a ${width}`)
    await page.screenshot({ path: `${DIR}/mas-${width}.png` })
    await page.keyboard.press('Escape')
    await page.getByRole('button', { name: /¿Qué necesitas\?/ }).first().click()
    await page.keyboard.type('emp')
    await expect(page.getByRole('option').first()).toBeVisible()
    await audit(page, `buscador a ${width}`)
    await page.screenshot({ path: `${DIR}/buscador-emp-${width}.png` })
    await page.keyboard.press('Escape')
  }
})

test('login: el acceso rápido de demostración entra en dos toques (Demo → cuenta)', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await page.getByRole('button', { name: 'Demo', exact: true }).click()
  const demo = page.getByRole('dialog', { name: 'Acceso rápido de demostración' })
  await expect(demo).toBeVisible()
  await audit(page, 'login con acceso rápido')
  await page.screenshot({ path: `${DIR}/login-demo-390.png`, fullPage: true })
  await demo.getByRole('button', { name: /Dueña/ }).click()
  await expect(page.getByRole('heading', { level: 1, name: /Hola/ })).toBeVisible()
})

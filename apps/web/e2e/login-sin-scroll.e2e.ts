import { expect, test, type Page } from '@playwright/test'

/**
 * Requisito de T21: entrar sin scroll. Logo, título, correo, contraseña, "Entrar", el error y los dos enlaces caben en
 * la primera vista a 390×844, 360×640, 1280×800 y 1366×768. Con zoom de texto al 125 % o con el teclado abierto se
 * permite desplazar (AA exige que el zoom funcione), pero nada se recorta. Capturas en e2e-artifacts/t21/.
 */
const DIR = 'e2e-artifacts/t21'
const SIZES = [
  { width: 390, height: 844 },
  { width: 360, height: 640 },
  { width: 1280, height: 800 },
  { width: 1366, height: 768 },
]

async function open(page: Page, size: { width: number; height: number }) {
  await page.setViewportSize(size)
  await page.goto('/')
  await expect(page.getByLabel('Correo')).toBeVisible()
  // Espera la fuente y las fotos: cambian la altura.
  await page.evaluate(async () => {
    await document.fonts.ready
    await Promise.all([...document.images].map((i) => (i.complete ? null : new Promise((r) => i.addEventListener('load', r, { once: true })))))
  })
}

/** La página no se desplaza y cada pieza clave está entera dentro de la ventana. */
async function fitsFirstView(page: Page, label: string) {
  const { scrollH, innerH, scrollW, innerW } = await page.evaluate(() => ({
    scrollH: document.documentElement.scrollHeight,
    innerH: window.innerHeight,
    scrollW: document.documentElement.scrollWidth,
    innerW: window.innerWidth,
  }))
  expect(scrollH, `scroll vertical en ${label}`).toBeLessThanOrEqual(innerH)
  expect(scrollW, `scroll horizontal en ${label}`).toBeLessThanOrEqual(innerW)
  for (const loc of [
    page.getByRole('heading', { level: 1, name: 'Cáterin' }),
    page.getByLabel('Correo'),
    page.getByLabel('Contraseña'),
    page.getByRole('button', { name: 'Entrar' }),
    page.getByRole('link', { name: /Crea tu cuenta/ }),
    page.getByRole('link', { name: /Eres cliente/ }),
  ]) {
    const box = await loc.boundingBox()
    expect(box, `${label}: sin caja`).not.toBeNull()
    expect(box!.y, `${label}: arriba de la ventana`).toBeGreaterThanOrEqual(0)
    expect(box!.y + box!.height, `${label}: bajo la ventana`).toBeLessThanOrEqual(innerH)
  }
}

async function showError(page: Page) {
  await page.route('**/api/v1/auth/login', (route) =>
    route.fulfill({
      status: 401,
      contentType: 'application/problem+json',
      body: JSON.stringify({ type: 'about:blank', title: 'Correo o contraseña incorrectos', status: 401, code: 'invalid_credentials' }),
    }),
  )
  await page.getByLabel('Correo').fill('nadie@ejemplo.cl')
  await page.getByLabel('Contraseña').fill('clave-equivocada')
  await page.getByRole('button', { name: 'Entrar' }).click()
  await expect(page.getByRole('alert')).toContainText('Correo o contraseña incorrectos')
}

for (const size of SIZES) {
  test(`entrar sin scroll a ${size.width}×${size.height}`, async ({ page }) => {
    await open(page, size)
    await fitsFirstView(page, `${size.width}×${size.height}`)
    await page.screenshot({ path: `${DIR}/login-sin-scroll-${size.width}x${size.height}.png` })
  })
}

test('con el error a la vista sigue sin scroll en 390×844, 1280×800 y 1366×768; en 360×640 nada se recorta', async ({ page }) => {
  for (const size of [SIZES[0], SIZES[2], SIZES[3]]) {
    await open(page, size)
    await showError(page)
    await fitsFirstView(page, `error ${size.width}×${size.height}`)
    await page.screenshot({ path: `${DIR}/login-error-${size.width}x${size.height}.png` })
    await page.unroute('**/api/v1/auth/login')
  }
  await open(page, SIZES[1])
  await showError(page)
  const button = page.getByRole('button', { name: 'Entrar' })
  await button.scrollIntoViewIfNeeded()
  await expect(button).toBeInViewport()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.screenshot({ path: `${DIR}/login-error-360x640.png`, fullPage: true })
})

test('con zoom de texto al 125 % se puede desplazar pero nada se recorta', async ({ page }) => {
  await open(page, SIZES[0])
  await page.addStyleTag({ content: 'html { font-size: 21.25px !important; }' }) // 17 px × 125 %
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  for (const name of [/Eres cliente/, /Crea tu cuenta/]) {
    const link = page.getByRole('link', { name })
    await link.scrollIntoViewIfNeeded()
    await expect(link).toBeInViewport({ ratio: 1 })
  }
  await page.screenshot({ path: `${DIR}/login-zoom125-390.png`, fullPage: true })
})

test('con el teclado abierto "Entrar" se alcanza sin pelear con la página', async ({ page }) => {
  await open(page, SIZES[0])
  await page.getByLabel('Correo').focus()
  // El teclado del celular deja ~520 px de alto visible: la página se puede desplazar y nada queda tapado.
  await page.setViewportSize({ width: 390, height: 520 })
  const button = page.getByRole('button', { name: 'Entrar' })
  await button.scrollIntoViewIfNeeded()
  await expect(button).toBeInViewport({ ratio: 1 })
  await expect(page.getByLabel('Correo')).toBeFocused()
  await page.screenshot({ path: `${DIR}/login-teclado-390x520.png` })
})

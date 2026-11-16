/** Catálogo del portal (T15, ADR-009): el cliente mira pymes y productos y pasa a cotizar con ellos elegidos. */
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from '../../App'
import { setAccessToken } from '../../api'
import { resetMemory } from '../../offline/db'
import { mockApi, session } from '../../test/mockApi'
import { pickShowcase, splitTitle } from './PortalPyme'

const customerSession = {
  ...session,
  user: { id: 'c1', email: 'ana@cliente.local', full_name: 'Ana Cliente', role: 'customer', is_active: true },
  pyme: { id: 'p1', name: 'Cocina Demo', commune: 'Temuco', vat_pct: '19.00', is_demo: true },
}

const pymes = [
  { id: 'p1', name: 'Cocina Demo', commune: 'Temuco', joined: true, description: null, logo_url: null },
  {
    id: 'p2',
    name: 'Banquetería Lago',
    commune: 'Villarrica',
    joined: false,
    description: 'Cóctel para matrimonios',
    logo_url: '/api/v1/portal/media/p2/logo.webp',
  },
]

const products = [
  { id: 'r-pino', name: 'Empanadas de pino', yield_unit: 'unit', description: 'Horneadas', category: 'Salados', photo_url: null },
  { id: 'r-queso', name: 'Empanadas de queso', yield_unit: 'unit', description: null, category: 'Salados', photo_url: null },
  { id: 'r-ceviche', name: 'Ceviche', yield_unit: 'g', description: null, category: 'Platos', photo_url: '/x.webp' },
]

function api(extra: Record<string, () => { status?: number; body: unknown }> = {}) {
  mockApi({
    'POST /auth/refresh': () => ({ body: customerSession }),
    'GET /portal/requests': () => ({ body: [] }),
    'GET /portal/pymes': () => ({ body: pymes }),
    'GET /portal/products': () => ({ body: products }),
    ...extra,
  })
}

beforeEach(() => {
  setAccessToken(null)
  resetMemory()
})
afterEach(() => vi.restoreAllMocks())

test('del inicio a cotizar con una pyme en 3 clics', async () => {
  window.location.hash = '#/'
  api()
  const user = userEvent.setup()
  render(<App />)
  await screen.findByRole('heading', { name: 'Mis cotizaciones' })
  // 1: "Pymes" en la navegación del cliente
  await user.click(screen.getAllByRole('link', { name: 'Pymes' })[0])
  expect(await screen.findByRole('heading', { name: 'Pymes de catering' })).toBeInTheDocument()
  expect(screen.getByText('Cóctel para matrimonios')).toBeInTheDocument()
  expect(screen.getByText('ya le cotizaste')).toBeInTheDocument() // Cocina Demo: joined
  // 2: la tarjeta de la pyme
  await user.click(screen.getByRole('link', { name: /^Banquetería Lago/ }))
  expect(await screen.findByRole('heading', { level: 1, name: 'Banquetería Lago' })).toBeInTheDocument()
  // 3: cotizar
  await user.click(await screen.findByRole('button', { name: 'Cotizar con esta pyme' }))
  await waitFor(() => expect(window.location.hash).toBe('#/cotizar?pyme=p2'))
  expect(await screen.findByLabelText(/A qué pyme le quieres cotizar/)).toHaveValue('p2')
})

test('agrupa por categoría, marca productos y los lleva a la cotización', async () => {
  window.location.hash = '#/pymes/p2'
  api()
  const user = userEvent.setup()
  render(<App />)
  expect(await screen.findByRole('heading', { level: 2, name: 'Salados' })).toBeInTheDocument()
  expect(screen.getByRole('heading', { level: 2, name: 'Platos' })).toBeInTheDocument()
  const platos = screen.getByRole('region', { name: 'Platos' })
  expect(within(platos).getByText('Por kilo')).toBeInTheDocument()
  expect(screen.queryByText(/\$/)).not.toBeInTheDocument() // sin precios en el catálogo (ADR-007)

  const pino = screen.getByRole('button', { name: /^Agregar.*Empanadas de pino$/ })
  await user.click(pino)
  expect(pino).toHaveAttribute('aria-pressed', 'true')
  await user.click(screen.getByRole('button', { name: /^Agregar.*Ceviche$/ }))
  await user.click(screen.getByRole('button', { name: 'Cotizar 2 productos' }))

  await waitFor(() => expect(window.location.hash).toBe('#/cotizar?pyme=p2&p=r-pino,r-ceviche'))
  // Llega directo al formulario con una línea por producto, la cantidad vacía y la unidad sugerida.
  const first = await screen.findByLabelText('Producto 1')
  await waitFor(() => expect(first).toHaveValue('r-pino'))
  expect(screen.getByLabelText('Producto 2')).toHaveValue('r-ceviche')
  const units = screen.getAllByLabelText('Unidad')
  await waitFor(() => expect(units[1]).toHaveValue('kg'))
  expect(units[0]).toHaveValue('unit')
  for (const qty of screen.getAllByLabelText('Cantidad')) expect(qty).toHaveValue('')
})

test('regla del producto destacado y del recomendado (T19)', () => {
  const plain = { yield_unit: 'unit' as const, category: null, description: null, photo_url: null }
  const a = { ...plain, id: 'a', name: 'A' }
  const b = { ...plain, id: 'b', name: 'B', description: 'con descripción' }
  const c = { ...plain, id: 'c', name: 'C', photo_url: '/c.webp' }
  const d = { ...plain, id: 'd', name: 'D', photo_url: '/d.webp' }
  expect(pickShowcase([a, b, c, d])).toEqual({ featured: c, recommended: d }) // con foto, en orden
  expect(pickShowcase([a, b])).toEqual({ featured: b, recommended: a }) // sin fotos: primero el que tiene descripción
  expect(pickShowcase([a])).toEqual({ featured: a, recommended: null })
  expect(pickShowcase([])).toEqual({ featured: null, recommended: null })
  expect(splitTitle('Empanadas de pino')).toEqual(['Empanadas', 'de pino'])
  expect(splitTitle('Ceviche')).toEqual(['', 'Ceviche'])
})

test('la portada destaca un producto y lleva a cotizarlo, sin precios (T19)', async () => {
  window.location.hash = '#/pymes/p2'
  api()
  const user = userEvent.setup()
  render(<App />)
  // Destacado: el primero con foto (Ceviche). Recomendado: el siguiente, con descripción (Empanadas de pino).
  const hero = await screen.findByRole('region', { name: 'Ceviche' })
  expect(within(hero).getByRole('heading', { level: 2, name: 'Ceviche' })).toBeInTheDocument()
  expect(within(hero).getByText('Por kilo')).toBeInTheDocument()
  expect(within(hero).getByText('Precio al cotizar')).toBeInTheDocument()
  expect(within(hero).getByText('Lo prepara')).toBeInTheDocument()
  expect(within(hero).getByText('Villarrica')).toBeInTheDocument()
  const rec = within(hero).getByRole('article', { name: 'Empanadas de pino' })
  expect(within(rec).getByText('Recomendado')).toBeInTheDocument()
  expect(screen.queryByText(/\$/)).not.toBeInTheDocument()

  // Marcar el recomendado también lo marca en la grilla, y el botón de la portada lo suma a la cotización.
  await user.click(within(rec).getByRole('button', { name: /Empanadas de pino, el recomendado$/ }))
  expect(screen.getByRole('button', { name: /^Agregado.*Empanadas de pino$/ })).toHaveAttribute('aria-pressed', 'true')
  await user.click(within(hero).getByRole('button', { name: 'Cotizar ceviche' }))
  await waitFor(() => expect(window.location.hash).toBe('#/cotizar?pyme=p2&p=r-ceviche,r-pino'))
})

test('descarta productos que no son de esa pyme', async () => {
  window.location.hash = '#/cotizar?pyme=p2&p=r-pino,de-otra-pyme'
  api()
  render(<App />)
  const first = await screen.findByLabelText('Producto 1')
  await waitFor(() => expect(first).toHaveValue('r-pino'))
  await waitFor(() => expect(screen.queryByLabelText('Producto 2')).not.toBeInTheDocument())
})

test('busca pymes por nombre o comuna, sin tildes', async () => {
  window.location.hash = '#/pymes'
  const many = [
    ...pymes,
    { id: 'p3', name: 'Dulces Pucón', commune: 'Pucón', joined: false, description: null, logo_url: null },
    { id: 'p4', name: 'Sabores del Lago', commune: 'Temuco', joined: false, description: null, logo_url: null },
  ]
  api({ 'GET /portal/pymes': () => ({ body: many }) })
  const user = userEvent.setup()
  render(<App />)
  await user.type(await screen.findByLabelText('Buscar por nombre o comuna'), 'pucon')
  const cards = screen.getAllByRole('link').filter((a) => a.getAttribute('href')?.startsWith('#/pymes/'))
  expect(cards).toHaveLength(1)
  expect(cards[0]).toHaveTextContent('Dulces Pucón')
  await user.clear(screen.getByLabelText('Buscar por nombre o comuna'))
  await user.type(screen.getByLabelText('Buscar por nombre o comuna'), 'xyz')
  expect(screen.getByText('No encontramos pymes con «xyz».')).toBeInTheDocument()
})

test('una pyme cerrada o inexistente lo dice y ofrece volver', async () => {
  window.location.hash = '#/pymes/p9'
  api({
    'GET /portal/products': () => ({
      status: 404,
      body: { code: 'pyme_not_available', title: 'Esa pyme no recibe cotizaciones en línea' },
    }),
  })
  render(<App />)
  expect(await screen.findByText('Esta pyme no está disponible en el portal.')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Ver todas las pymes' })).toBeInTheDocument()
})

test('una pyme sin productos publicados deja cotizar igual', async () => {
  window.location.hash = '#/pymes/p1'
  api({ 'GET /portal/products': () => ({ body: [] }) })
  render(<App />)
  expect(await screen.findByText(/todavía no publica productos/)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Cotizar con esta pyme' })).toBeInTheDocument()
})

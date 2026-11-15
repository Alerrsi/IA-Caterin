/** Lo que la dueña publica en el catálogo del portal (T15, ADR-009): logo, presentación y datos de cada producto. */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from '../App'
import { setAccessToken } from '../api'
import { resetMemory } from '../offline/db'
import { calls, mockApi, session, type Routes } from '../test/mockApi'

const pyme = {
  id: 'p1',
  name: 'Cocina Demo',
  rut: null,
  commune: 'Temuco',
  default_waste_pct: '5.00',
  default_margin_pct: '40.00',
  vat_pct: '19.00',
  prices_include_vat: true,
  quote_validity_days: 15,
  is_demo: true,
  customer_code: null,
  description: null,
  logo_url: null,
}
const recipe = {
  id: 'r1',
  name: 'Empanadas de pino',
  yield_qty: '12.000',
  yield_unit: 'unit',
  is_final_product: true,
  vision_class: null,
  notes: null,
  version: 1,
  is_active: true,
  catalog_description: null,
  category: null,
  visible_in_catalog: true,
  photo_url: null,
  lines: [],
}

const as = (role: string): Routes => ({
  'POST /auth/refresh': () => ({ body: { ...session, user: { ...session.user, role } } }),
  'GET /pyme': () => ({ body: pyme }),
  'PATCH /pyme': (body) => ({ body: { ...pyme, ...(body as object) } }),
  'PUT /pyme/logo': () => ({ body: { ...pyme, logo_url: '/api/v1/portal/media/p1/logo.webp' } }),
  'GET /users': () => ({ body: [] }),
  'GET /recipes/r1': () => ({ body: recipe }),
  'GET /recipes/r1/cost': () => ({ status: 404, body: { code: 'x', title: 'x' } }),
  'PATCH /recipes/r1': (body) => ({ body: { ...recipe, ...(body as object) } }),
  'PUT /recipes/r1/photo': () => ({ body: { ...recipe, photo_url: '/api/v1/portal/media/p1/foto.webp' } }),
})

beforeEach(() => {
  setAccessToken(null)
  resetMemory()
})
afterEach(() => vi.restoreAllMocks())

const file = (bytes: number, name = 'logo.png') => new File([new Uint8Array(bytes)], name, { type: 'image/png' })

test('la dueña sube su logo y escribe la presentación de su pyme', async () => {
  window.location.hash = '#/ajustes'
  mockApi(as('owner'))
  const user = userEvent.setup()
  render(<App />)
  expect(await screen.findByRole('heading', { name: 'Tu vitrina en el portal' })).toBeInTheDocument()
  await user.upload(await screen.findByLabelText('Logo de tu pyme'), file(1000))
  await waitFor(() => expect(calls.some((c) => c.method === 'PUT' && c.path === '/pyme/logo')).toBe(true))
  expect(await screen.findByRole('button', { name: 'Cambiar imagen' })).toBeInTheDocument()

  await user.type(screen.getByLabelText(/^Presentación corta/), 'Cocina casera del sur')
  expect(screen.getByText('21 de 280 caracteres')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Guardar presentación' }))
  await waitFor(() =>
    expect(calls.find((c) => c.method === 'PATCH' && c.path === '/pyme')?.body).toEqual({
      description: 'Cocina casera del sur',
    }),
  )
})

test('una imagen de más de 2 MB se avisa sin subirla', async () => {
  window.location.hash = '#/ajustes'
  mockApi(as('owner'))
  const user = userEvent.setup()
  render(<App />)
  await user.upload(await screen.findByLabelText('Logo de tu pyme'), file(2 * 1024 * 1024 + 1))
  expect(await screen.findByText(/pesa más de 2 MB/)).toBeInTheDocument()
  expect(calls.some((c) => c.method === 'PUT')).toBe(false)
})

test('la dueña publica la foto, la descripción y la categoría de un producto, o lo oculta', async () => {
  window.location.hash = '#/recetas/r1'
  mockApi(as('owner'))
  const user = userEvent.setup()
  render(<App />)
  expect(await screen.findByRole('heading', { name: 'En el catálogo del portal' })).toBeInTheDocument()
  await user.upload(screen.getByLabelText('Foto del producto'), file(5000, 'pino.jpg'))
  await waitFor(() => expect(calls.some((c) => c.method === 'PUT' && c.path === '/recipes/r1/photo')).toBe(true))
  await user.type(screen.getByLabelText('Descripción para los clientes'), 'Horneadas el mismo día')
  await user.type(screen.getByLabelText(/^Categoría/), 'Salados')
  await user.click(screen.getByLabelText(/Mostrar a los clientes/))
  await user.click(screen.getByRole('button', { name: 'Guardar catálogo' }))
  await waitFor(() =>
    expect(calls.find((c) => c.method === 'PATCH' && c.path === '/recipes/r1')?.body).toEqual({
      catalog_description: 'Horneadas el mismo día',
      category: 'Salados',
      visible_in_catalog: false,
    }),
  )
})

test('la colaboradora no ve el panel del catálogo', async () => {
  window.location.hash = '#/recetas/r1'
  mockApi(as('collaborator'))
  render(<App />)
  expect(await screen.findByRole('heading', { name: 'Empanadas de pino' })).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'En el catálogo del portal' })).not.toBeInTheDocument()
})

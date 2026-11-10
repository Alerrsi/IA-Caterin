import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from '../App'
import { setAccessToken } from '../api'
import { resetMemory } from '../offline/db'
import { calls, mockApi, session } from '../test/mockApi'

const ing = (id: string, name: string, base_unit: string) => ({
  id, name, base_unit, stock_qty: '1000.000', min_stock_qty: null, waste_pct: null, category: null,
  is_active: true, is_low: false, updated_at: 'x',
})
const ingredients = [ing('i-harina', 'Harina sin polvos', 'g'), ing('i-huevo', 'Huevo', 'unit'), ing('i-leche', 'Leche', 'ml')]

const routes = (items = ingredients) => ({
  'POST /auth/refresh': () => ({ body: session }),
  'GET /ingredients': () => ({ body: { items, next_cursor: null } }),
  'POST /recipes': () => ({ status: 201, body: { id: 'r-new', name: 'Queque', lines: [] } }),
  'GET /recipes/r-new': () => ({
    body: { id: 'r-new', name: 'Queque', yield_qty: '1500.000', yield_unit: 'g', is_final_product: true, vision_class: null,
      notes: null, version: 1, is_active: true, updated_at: 'x', lines: [] },
  }),
  'GET /recipes/r-new/cost': () => ({ status: 404, body: { code: 'x', title: 'x' } }),
})

beforeEach(() => {
  resetMemory()
  window.location.hash = '#/recetas/nueva'
  setAccessToken(null)
})
afterEach(() => vi.restoreAllMocks())

test('crea una receta: convierte el rendimiento a la unidad base y envía las líneas con su unidad', async () => {
  mockApi(routes())
  const user = userEvent.setup()
  render(<App />)
  await user.type(await screen.findByLabelText('Nombre de la receta'), 'Queque')
  await user.type(screen.getByLabelText('Rinde (cantidad)'), '1,5')
  await user.selectOptions(screen.getByLabelText('Unidad del rendimiento'), 'kg')
  await user.type(screen.getByLabelText(/Nombre para el conteo por foto/), 'queque')

  const line1 = screen.getByRole('group', { name: 'Insumo 1' })
  await user.type(within(line1).getByLabelText('Buscar insumo'), 'harin')
  expect(within(line1).getAllByRole('option').map((o) => o.textContent)).toEqual(['Elige un insumo', 'Harina sin polvos'])
  await user.selectOptions(within(line1).getByLabelText('Insumo'), 'i-harina')
  await user.type(within(line1).getByLabelText('Cantidad'), '0,5')
  expect(within(line1).getByLabelText('Unidad')).toHaveValue('kg')
  await user.type(within(line1).getByLabelText('Merma (%) opcional'), '5')

  await user.click(screen.getByRole('button', { name: 'Agregar otro insumo' }))
  const line2 = screen.getByRole('group', { name: 'Insumo 2' })
  await user.selectOptions(within(line2).getByLabelText('Insumo'), 'i-huevo')
  await user.type(within(line2).getByLabelText('Cantidad'), '1')
  await user.selectOptions(within(line2).getByLabelText('Unidad'), 'docena')

  await user.click(screen.getByRole('button', { name: 'Guardar receta' }))
  expect(await screen.findByRole('heading', { name: 'Queque' })).toBeInTheDocument()
  expect(window.location.hash).toBe('#/recetas/r-new')
  expect(calls.find((c) => c.method === 'POST' && c.path === '/recipes')?.body).toEqual({
    name: 'Queque',
    yield_qty: '1500',
    yield_unit: 'g',
    is_final_product: true,
    vision_class: 'queque',
    lines: [
      { ingredient_id: 'i-harina', qty: '0.5', unit: 'kg', waste_pct: '5' },
      { ingredient_id: 'i-huevo', qty: '1', unit: 'docena', waste_pct: null },
    ],
  })
})

test('valida antes de enviar: nombre, rendimiento, insumo, cantidad y repetidos', async () => {
  mockApi(routes())
  const user = userEvent.setup()
  render(<App />)
  const save = await screen.findByRole('button', { name: 'Guardar receta' })
  await user.click(save)
  expect(screen.getByRole('alert')).toHaveTextContent('Escribe el nombre de la receta')
  await user.type(screen.getByLabelText('Nombre de la receta'), 'Queque')
  await user.click(save)
  expect(screen.getByRole('alert')).toHaveTextContent('El rendimiento debe ser mayor que cero')
  await user.type(screen.getByLabelText('Rinde (cantidad)'), '12')
  await user.click(save)
  expect(screen.getByRole('alert')).toHaveTextContent('Elige el insumo 1')
  const line1 = screen.getByRole('group', { name: 'Insumo 1' })
  await user.selectOptions(within(line1).getByLabelText('Insumo'), 'i-leche')
  await user.click(save)
  expect(screen.getByRole('alert')).toHaveTextContent('La cantidad del insumo 1 debe ser mayor que cero')
  await user.type(within(line1).getByLabelText('Cantidad'), '200')
  await user.click(screen.getByRole('button', { name: 'Agregar otro insumo' }))
  const line2 = screen.getByRole('group', { name: 'Insumo 2' })
  await user.selectOptions(within(line2).getByLabelText('Insumo'), 'i-leche')
  await user.type(within(line2).getByLabelText('Cantidad'), '100')
  await user.click(save)
  expect(screen.getByRole('alert')).toHaveTextContent('Leche está dos veces')
  await user.click(screen.getByRole('button', { name: 'Quitar insumo 2' }))
  expect(screen.queryByRole('group', { name: 'Insumo 2' })).not.toBeInTheDocument()
  expect(calls.some((c) => c.method === 'POST' && c.path === '/recipes')).toBe(false)
})

test('muestra el error de la API y sin insumos explica qué hacer primero', async () => {
  mockApi({ ...routes(), 'POST /recipes': () => ({ status: 409, body: { code: 'recipe_exists', title: 'Ya tienes una receta con ese nombre' } }) })
  const user = userEvent.setup()
  const { unmount } = render(<App />)
  await user.type(await screen.findByLabelText('Nombre de la receta'), 'Queque')
  await user.type(screen.getByLabelText('Rinde (cantidad)'), '12')
  const line1 = screen.getByRole('group', { name: 'Insumo 1' })
  await user.selectOptions(within(line1).getByLabelText('Insumo'), 'i-huevo')
  await user.type(within(line1).getByLabelText('Cantidad'), '3')
  await user.click(screen.getByRole('button', { name: 'Guardar receta' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Ya tienes una receta con ese nombre')
  unmount()

  vi.restoreAllMocks()
  resetMemory()
  mockApi(routes([]))
  render(<App />)
  expect(await screen.findByText(/Primero carga tus insumos/)).toBeInTheDocument()
})

test('desde Recetas se llega con un toque', async () => {
  window.location.hash = '#/recetas'
  mockApi({ ...routes(), 'GET /recipes': () => ({ body: [] }) })
  const user = userEvent.setup()
  render(<App />)
  await user.click(await screen.findByRole('button', { name: 'Nueva receta' }))
  expect(await screen.findByLabelText('Nombre de la receta')).toBeInTheDocument()
})

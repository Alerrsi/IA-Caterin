import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from './App'
import { setAccessToken } from './api'
import { resetMemory } from './offline/db'
import { editDistance, normalize, scoreItem, search, type FindItem } from './quickfind'
import { remember, recentFor } from './recent'
import { goBack, navigate, recordVisit, resetTrail } from './router'
import { mockApi, session } from './test/mockApi'

// --------------------------------------------------------------------------- búsqueda (pura)

const item = (id: string, group: FindItem['group'], label: string, keywords = ''): FindItem => ({
  id,
  group,
  label,
  path: `/${id}`,
  keywords,
})

test('normaliza sin tildes ni signos', () => {
  expect(normalize('  Ají de COLOR, ¡rico! ')).toBe('aji de color rico')
  expect(editDistance('arina', 'harina', 1)).toBe(1)
  expect(editDistance('azucar', 'harina', 1)).toBe(2)
})

test('encuentra sin tildes, por prefijo, por palabra clave y con un error de tipeo', () => {
  const items = [
    item('aji', 'ingredients', 'Ají de color'),
    item('harina', 'ingredients', 'Harina sin polvos'),
    item('emp', 'recipes', 'Empanadas de pino'),
    item('quote', 'actions', 'Cotizar un pedido', 'presupuesto cliente'),
  ]
  expect(search('aji', items).map((r) => r.id)).toEqual(['aji'])
  expect(search('emp pin', items).map((r) => r.id)).toEqual(['emp'])
  expect(search('arina', items).map((r) => r.id)).toEqual(['harina']) // falta la h
  expect(search('presupuesto', items).map((r) => r.id)).toEqual(['quote'])
  expect(search('xyz', items)).toEqual([])
  expect(search('emp', [item('m', 'actions', 'Métricas', 'tiempo encuesta')])).toEqual([]) // no por un trozo de clave
  expect(scoreItem('harina', items[1])).toBeGreaterThan(scoreItem('arina', items[1]))
})

test('agrupa en orden fijo, limita a 8 y sin consulta sugiere acciones', () => {
  const items = [
    ...Array.from({ length: 12 }, (_, i) => item(`ing${i}`, 'ingredients', `Queso ${i}`)),
    item('rec', 'recipes', 'Queso de cabra'),
    item('act', 'actions', 'Queso del día'),
  ]
  const out = search('queso', items)
  expect(out).toHaveLength(8)
  expect(out[0].group).toBe('actions')
  const groups = out.map((r) => r.group)
  expect(groups).toEqual([...groups].sort((a, b) => ['actions', 'ingredients', 'recipes'].indexOf(a) - ['actions', 'ingredients', 'recipes'].indexOf(b)))
  expect(search('', items).map((r) => r.id)).toEqual(['act'])
})

// --------------------------------------------------------------------------- volver y recientes

test('volver regresa a la pantalla anterior de la app o, si se entró directo, al padre', () => {
  const back = vi.spyOn(window.history, 'back').mockImplementation(() => {})
  window.location.hash = '#/recetas/r1'
  resetTrail('/recetas/r1')
  goBack('/recetas')
  expect(back).not.toHaveBeenCalled()
  expect(window.location.hash).toBe('#/recetas')

  resetTrail('/pedidos')
  window.location.hash = '#/recetas/r1'
  recordVisit('/recetas/r1')
  goBack('/recetas')
  expect(back).toHaveBeenCalledTimes(1)
  back.mockRestore()
})

test('después de guardar, la pantalla nueva reemplaza al formulario: volver no regresa al formulario', async () => {
  const back = vi.spyOn(window.history, 'back').mockImplementation(() => {})
  const changed = () => new Promise((resolve) => window.addEventListener('hashchange', resolve, { once: true }))
  window.location.hash = '#/'
  resetTrail('/')
  let wait = changed()
  window.location.hash = '#/recetas/nueva'
  await wait
  wait = changed()
  navigate('/recetas/r9', { replace: true })
  await wait
  navigate('/recetas/r9', { replace: true }) // misma ruta: no hay hashchange y no debe quedar marcado
  recordVisit('/inventario') // se suma (no reemplaza a la receta)
  recordVisit('/recetas/r9') // atrás
  // El rastro es ['/', '/recetas/r9']: al volver al inicio se reconoce como "atrás" y desde ahí no hay anterior.
  recordVisit('/')
  window.location.hash = '#/'
  goBack('/fallback')
  expect(back).not.toHaveBeenCalled()
  expect(window.location.hash).toBe('#/fallback')
  back.mockRestore()
})

test('recientes: últimos 3, sin repetir y por persona', () => {
  localStorage.clear()
  for (const n of ['a', 'b', 'c', 'd']) remember('u1', { path: `/recetas/${n}`, label: n, kind: 'recipe' })
  remember('u1', { path: '/recetas/c', label: 'c', kind: 'recipe' })
  expect(recentFor('u1').map((i) => i.label)).toEqual(['c', 'd', 'b'])
  expect(recentFor('u2')).toEqual([])
})

// --------------------------------------------------------------------------- en la app

const ingredients = [
  {
    id: 'har',
    name: 'Harina sin polvos',
    base_unit: 'g',
    stock_qty: '2500.000',
    min_stock_qty: '10000.000',
    waste_pct: null,
    category: null,
    is_active: true,
    is_low: true,
    updated_at: '2026-11-09T12:00:00Z',
  },
  {
    id: 'sal',
    name: 'Sal',
    base_unit: 'g',
    stock_qty: '3000.000',
    min_stock_qty: null,
    waste_pct: null,
    category: null,
    is_active: true,
    is_low: false,
    updated_at: '2026-11-09T12:00:00Z',
  },
]

const orders = [
  { id: 'o1', customer_name: 'Matrimonio Soto', event_date: '2026-11-20', status: 'requested', lines: [], guests: 80 },
  { id: 'o2', customer_name: 'Colegio Los Robles', event_date: '2026-12-20', status: 'confirmed', lines: [], guests: 40 },
]

function routes() {
  return {
    'POST /auth/refresh': () => ({ body: session }),
    'GET /ingredients': () => ({ body: { items: ingredients, next_cursor: null } }),
    'GET /recipes': () => ({ body: [] }),
    'GET /products/stock': () => ({ body: [] }),
    'GET /orders': () => ({ body: orders }),
    'GET /prices': () => ({ body: [] }),
  }
}

beforeEach(() => {
  resetMemory()
  window.location.hash = ''
  setAccessToken(null)
})
afterEach(() => vi.restoreAllMocks())

test('Ctrl+K abre el buscador; "arina" encuentra el insumo y Enter lo abre', async () => {
  mockApi(routes())
  const user = userEvent.setup()
  render(<App />)
  await screen.findByRole('heading', { level: 1 })
  await user.keyboard('{Control>}k{/Control}')
  const box = await screen.findByRole('combobox', { name: 'Buscar en Cáterin' })
  expect(box).toHaveFocus()
  await user.type(box, 'arina')
  const option = await screen.findByRole('option', { name: /Harina sin polvos/ })
  expect(option).toHaveAttribute('aria-selected', 'true')
  expect(box).toHaveAttribute('aria-activedescendant', option.id)
  await user.keyboard('{Enter}')
  await waitFor(() => expect(window.location.hash).toBe('#/inventario/har'))
  expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
})

test('el buscador encuentra acciones y pedidos por cliente; Esc lo cierra', async () => {
  mockApi(routes())
  const user = userEvent.setup()
  render(<App />)
  await screen.findByRole('heading', { level: 1 })
  await user.click(screen.getAllByRole('button', { name: /¿Qué necesitas\?/ })[0])
  const box = await screen.findByRole('combobox')
  await user.type(box, 'soto')
  expect(await screen.findByRole('option', { name: /Matrimonio Soto/ })).toBeInTheDocument()
  await user.clear(box)
  await user.type(box, 'presupuesto')
  expect(await screen.findByRole('option', { name: /Cotizar un pedido/ })).toBeInTheDocument()
  await user.keyboard('{Escape}')
  expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
})

test('"Más" agrupa el resto, atrapa el foco y se cierra con Esc', async () => {
  mockApi(routes())
  const user = userEvent.setup()
  render(<App />)
  await screen.findByRole('heading', { level: 1 })
  const bar = screen.getByRole('navigation', { name: 'Navegación principal' })
  expect(within(bar).getAllByRole('link').map((a) => a.textContent)).toEqual(['Inicio', 'Cotizar', 'Foto', 'Inventario'])
  await user.click(within(bar).getByRole('button', { name: 'Más' }))
  const sheet = await screen.findByRole('dialog', { name: 'Todo Cáterin' })
  for (const group of ['Ventas', 'Cocina', 'Administración']) expect(within(sheet).getByRole('heading', { name: group })).toBeInTheDocument()
  expect(within(sheet).getByRole('link', { name: /Mi negocio/ })).toHaveAttribute('href', '#/tablero')
  // Foco atrapado: Tab desde el último vuelve al primero.
  const focusables = within(sheet).getAllByRole('button').concat(within(sheet).getAllByRole('link'))
  expect(focusables.length).toBeGreaterThan(5)
  within(sheet).getByRole('button', { name: 'Cerrar sesión' }).focus()
  await user.tab()
  expect(sheet.contains(document.activeElement)).toBe(true)
  await user.keyboard('{Escape}')
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

test('los avisos del inicio abren la vista filtrada y "Ver todos" la limpia', async () => {
  mockApi({ ...routes(), 'GET /orders': () => ({ body: orders }) })
  const user = userEvent.setup()
  render(<App />)
  await user.click(await screen.findByRole('button', { name: /1 insumo bajo el mínimo/ }))
  await waitFor(() => expect(window.location.hash).toBe('#/inventario?bajo=1'))
  expect(await screen.findByRole('checkbox', { name: 'Solo lo que falta' })).toBeChecked()
  expect(await screen.findByText('Harina sin polvos')).toBeInTheDocument()
  expect(screen.queryByText('Sal')).not.toBeInTheDocument()

  window.location.hash = '#/pedidos?estado=requested'
  expect(await screen.findByText('Mostrando solo las solicitudes por responder.')).toBeInTheDocument()
  expect(await screen.findByText('Matrimonio Soto')).toBeInTheDocument()
  expect(screen.queryByText('Colegio Los Robles')).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Ver todos' }))
  expect(await screen.findByText('Colegio Los Robles')).toBeInTheDocument()
})

test('saltar al contenido y, al cambiar de pantalla, el foco va al título', async () => {
  mockApi(routes())
  const user = userEvent.setup()
  render(<App />)
  await screen.findByRole('heading', { level: 1 })
  await user.tab()
  const skip = screen.getByRole('button', { name: 'Saltar al contenido' })
  expect(skip).toHaveFocus()
  await user.keyboard('{Enter}')
  expect(document.getElementById('contenido')).toHaveFocus()

  window.location.hash = '#/recetas'
  const title = await screen.findByRole('heading', { level: 1, name: 'Recetas' })
  await waitFor(() => expect(title).toHaveFocus())
  expect(screen.getByText('Pantalla: Recetas')).toBeInTheDocument()
})

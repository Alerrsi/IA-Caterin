import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from '../App'
import { setAccessToken } from '../api'
import { calls, mockApi, session, type Routes } from '../test/mockApi'

const preview = {
  total_rows: 3,
  valid: [
    { row: 2, name: 'Harina integral', base_unit: 'g', stock_qty: '5000', min_stock_qty: null, waste_pct: null, category: 'Abarrotes' },
    { row: 3, name: 'Huevo de campo', base_unit: 'unit', stock_qty: '60', min_stock_qty: '30', waste_pct: null, category: null },
  ],
  errors: [{ row: 4, field: 'unidad', message: 'No conozco la unidad «sacos»' }],
}

const routes: Routes = {
  'POST /auth/refresh': () => ({ body: session }),
  'POST /imports/ingredients/preview': () => ({ body: preview }),
  'POST /imports/ingredients/confirm': () => ({ body: { import_batch_id: 'b1', created: 2, suppliers_created: 0 } }),
  'DELETE /imports/b1': () => ({ body: {} }),
}

beforeEach(() => {
  window.location.hash = '#/importar'
  setAccessToken(null)
})
afterEach(() => vi.restoreAllMocks())

async function upload(user: ReturnType<typeof userEvent.setup>) {
  const file = new File(['nombre;unidad;stock\n'], 'insumos.csv', { type: 'text/csv' })
  await user.upload(await screen.findByLabelText(/Planilla/), file)
  await user.click(screen.getByRole('button', { name: 'Revisar planilla' }))
}

test('revisa la planilla, muestra errores por fila, carga las válidas y deshace', async () => {
  mockApi(routes)
  const user = userEvent.setup()
  render(<App />)
  await upload(user)
  expect(await screen.findByText('2 de 3 filas están bien.')).toBeInTheDocument()
  expect(screen.getByText('Harina integral')).toBeInTheDocument()
  expect(screen.getByText(/Fila 4 · unidad: No conozco la unidad «sacos»/)).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: 'Cargar 2 filas' }))
  expect(await screen.findByText('Se cargaron 2 filas.')).toBeInTheDocument()
  expect(calls.find((c) => c.path === '/imports/ingredients/confirm')?.body).toEqual({ rows: preview.valid })

  await user.click(screen.getByRole('button', { name: 'Deshacer esta carga' }))
  expect(await screen.findByText('Carga deshecha.')).toBeInTheDocument()
  expect(calls.some((c) => c.method === 'DELETE' && c.path === '/imports/b1')).toBe(true)
})

test('precios: marca proveedores nuevos y envía el source del preview', async () => {
  mockApi({
    ...routes,
    'POST /imports/prices/preview': () => ({
      body: {
        total_rows: 1,
        source: 'excel',
        errors: [],
        valid: [
          {
            row: 2,
            ingredient_id: 'i1',
            ingredient_name: 'Harina sin polvos',
            supplier_name: 'Molino Nuevo',
            supplier_is_new: true,
            package_label: 'saco 25 kg',
            package_qty: '25000',
            price_clp: 21000,
            includes_vat: true,
            price_date: '2026-11-02',
          },
        ],
      },
    }),
    'POST /imports/prices/confirm': () => ({ body: { import_batch_id: 'b2', created: 1, suppliers_created: 1 } }),
  })
  const user = userEvent.setup()
  render(<App />)
  await user.click(await screen.findByLabelText('Precios de proveedores'))
  await upload(user)
  expect(await screen.findByText(/Molino Nuevo \(proveedor nuevo\)/)).toBeInTheDocument()
  expect(screen.getByText(/\$21\.000/)).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Cargar 1 fila' }))
  expect(await screen.findByText(/Se cargó 1 fila\. Se creó 1 proveedor\./)).toBeInTheDocument()
  const body = calls.find((c) => c.path === '/imports/prices/confirm')?.body as { source: string }
  expect(body.source).toBe('excel')
})

test('sin filas válidas no deja cargar', async () => {
  mockApi({ ...routes, 'POST /imports/ingredients/preview': () => ({ body: { ...preview, valid: [], total_rows: 1 } }) })
  const user = userEvent.setup()
  render(<App />)
  await upload(user)
  expect(await screen.findByText(/Ninguna fila se puede cargar/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /^Cargar/ })).not.toBeInTheDocument()
})

test('solo la dueña puede importar', async () => {
  mockApi({ ...routes, 'POST /auth/refresh': () => ({ body: { ...session, user: { ...session.user, role: 'collaborator' } } }) })
  render(<App />)
  expect(await screen.findByText('Solo la dueña puede importar planillas.')).toBeInTheDocument()
})

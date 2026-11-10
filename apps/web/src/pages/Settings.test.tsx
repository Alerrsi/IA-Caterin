import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from '../App'
import { setAccessToken } from '../api'
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
}
const users = [
  { id: 'u1', email: 'duena@demo.local', full_name: 'Dueña Demo', role: 'owner', is_active: true },
  { id: 'u2', email: 'ana@demo.local', full_name: 'Ana Colaboradora', role: 'collaborator', is_active: false },
]

const owner: Routes = {
  'POST /auth/refresh': () => ({ body: session }),
  'GET /pyme': () => ({ body: pyme }),
  'PATCH /pyme': (body) => ({ body: { ...pyme, ...(body as object) } }),
  'GET /users': () => ({ body: users }),
  'POST /users': (body) => ({ body: { id: 'u3', role: 'collaborator', is_active: true, ...(body as object) } }),
}

beforeEach(() => {
  window.location.hash = '#/ajustes'
  setAccessToken(null)
})
afterEach(() => vi.restoreAllMocks())

test('muestra la configuración y el equipo, y guarda con PATCH (acepta coma decimal)', async () => {
  mockApi(owner)
  const user = userEvent.setup()
  render(<App />)
  const margin = await screen.findByLabelText(/^Margen de ganancia/)
  expect(margin).toHaveValue('40')
  expect(screen.getByLabelText(/^IVA/)).toHaveValue('19')
  expect(await screen.findByText('Ana Colaboradora')).toBeInTheDocument()
  expect(screen.getByText(/Colaboradora · Desactivada/)).toBeInTheDocument()

  await user.clear(margin)
  await user.type(margin, '35,5')
  await user.click(screen.getByRole('button', { name: 'Guardar ajustes' }))
  expect(await screen.findByText('Ajustes guardados.')).toBeInTheDocument()
  expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({
    name: 'Cocina Demo',
    default_margin_pct: '35.5',
    default_waste_pct: '5',
    vat_pct: '19',
    quote_validity_days: 15,
    prices_include_vat: true,
  })
})

test('valida los porcentajes antes de enviar', async () => {
  mockApi(owner)
  const user = userEvent.setup()
  render(<App />)
  const waste = await screen.findByLabelText(/^Merma por defecto/)
  await user.clear(waste)
  await user.type(waste, '150')
  await user.click(screen.getByRole('button', { name: 'Guardar ajustes' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Revisa los porcentajes')
  expect(calls.some((c) => c.method === 'PATCH')).toBe(false)
})

test('invita a una colaboradora', async () => {
  mockApi(owner)
  const user = userEvent.setup()
  render(<App />)
  await screen.findByText('Ana Colaboradora')
  const send = screen.getByRole('button', { name: 'Crear cuenta' })
  expect(send).toBeDisabled()
  await user.type(screen.getByLabelText(/^Nombre$/), 'Rosa Pérez')
  await user.type(screen.getByLabelText(/^Correo/), 'rosa@demo.local')
  await user.type(screen.getByLabelText(/^Contraseña inicial/), 'clave-segura-123')
  await user.click(send)
  expect(await screen.findByText('Listo: Rosa Pérez ya puede entrar.')).toBeInTheDocument()
  expect(calls.find((c) => c.method === 'POST' && c.path === '/users')?.body).toEqual({
    email: 'rosa@demo.local',
    full_name: 'Rosa Pérez',
    password: 'clave-segura-123',
    role: 'collaborator',
  })
  expect(screen.getByText('rosa@demo.local')).toBeInTheDocument()
})

test('la colaboradora no puede cambiar los ajustes', async () => {
  mockApi({ ...owner, 'POST /auth/refresh': () => ({ body: { ...session, user: { ...session.user, role: 'collaborator' } } }) })
  render(<App />)
  expect(await screen.findByText(/Solo la dueña puede cambiar los ajustes/)).toBeInTheDocument()
  await waitFor(() => expect(calls.some((c) => c.path === '/pyme')).toBe(false))
})

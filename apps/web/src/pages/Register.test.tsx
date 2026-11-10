import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from '../App'
import { setAccessToken } from '../api'
import { calls, mockApi, session } from '../test/mockApi'

beforeEach(() => {
  window.location.hash = '#/registro'
  setAccessToken(null)
})
afterEach(() => vi.restoreAllMocks())

async function fill(user: ReturnType<typeof userEvent.setup>) {
  await user.type(await screen.findByLabelText('Nombre de tu pyme'), 'Cocina Nueva')
  await user.type(screen.getByLabelText('Tu nombre'), 'Marta Soto')
  await user.type(screen.getByLabelText('Correo'), 'marta@demo.local')
  await user.type(screen.getByLabelText(/^Contraseña/), 'clave-segura-123')
  await user.click(screen.getByRole('button', { name: 'Crear cuenta' }))
}

test('crea la cuenta y entra a la app', async () => {
  mockApi({
    'POST /auth/refresh': () => ({ status: 401, body: { code: 'unauthorized', title: 'Necesitas iniciar sesión' } }),
    'POST /auth/register': () => ({ status: 201, body: { ...session, user: { ...session.user, full_name: 'Marta Soto' } } }),
  })
  const user = userEvent.setup()
  render(<App />)
  await fill(user)
  expect(await screen.findByText('Hola, Marta')).toBeInTheDocument()
  expect(calls.find((c) => c.path === '/auth/register')?.body).toEqual({
    pyme_name: 'Cocina Nueva',
    full_name: 'Marta Soto',
    email: 'marta@demo.local',
    password: 'clave-segura-123',
  })
})

test('muestra el error si el correo ya existe', async () => {
  mockApi({
    'POST /auth/refresh': () => ({ status: 401, body: { code: 'unauthorized', title: 'Necesitas iniciar sesión' } }),
    'POST /auth/register': () => ({ status: 409, body: { code: 'email_taken', title: 'Ese correo ya tiene cuenta' } }),
  })
  const user = userEvent.setup()
  render(<App />)
  await fill(user)
  expect(await screen.findByRole('alert')).toHaveTextContent('Ese correo ya tiene cuenta')
  expect(screen.getByRole('heading', { name: 'Crear cuenta' })).toBeInTheDocument()
})

test('desde el login se llega al registro y se puede volver', async () => {
  window.location.hash = ''
  mockApi({ 'POST /auth/refresh': () => ({ status: 401, body: { code: 'unauthorized', title: 'x' } }) })
  const user = userEvent.setup()
  render(<App />)
  await user.click(await screen.findByRole('link', { name: /Crea tu cuenta/ }))
  expect(await screen.findByLabelText('Nombre de tu pyme')).toBeInTheDocument()
  await user.click(screen.getByRole('link', { name: 'Ya tengo cuenta' }))
  expect(await screen.findByRole('button', { name: 'Entrar' })).toBeInTheDocument()
})

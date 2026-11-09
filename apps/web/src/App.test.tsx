import { render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import App from './App'

afterEach(() => vi.restoreAllMocks())

test('muestra el estado del servidor', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify({ status: 'ok' }), { status: 200 }),
  )
  render(<App />)
  expect(await screen.findByText('Conectado al servidor')).toBeInTheDocument()
})

test('avisa cuando no hay conexión', async () => {
  vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('offline'))
  render(<App />)
  expect(await screen.findByText('Sin conexión con el servidor')).toBeInTheDocument()
})

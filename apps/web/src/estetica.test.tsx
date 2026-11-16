/** Estética de la referencia (T21, ADR-013): botón en píldora, atajos, tarjetas, cifras, fuente y piezas de comida. */
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { fireEvent, render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import { Plate } from './components/Food'
import { Button, Cells, Kbd, Num } from './components/ui'
import { isTyping, useShortcut } from './shortcuts'

const read = (f: string) => readFileSync(resolve(__dirname, f), 'utf8')

test('el botón principal es una píldora de 48 px con foco visible, sombra suave y respeta reducir movimiento', () => {
  render(<Button>Cotizar</Button>)
  const cls = screen.getByRole('button', { name: 'Cotizar' }).className
  expect(cls).toContain('min-h-12')
  expect(cls).toContain('focus-visible:ring-4')
  expect(cls).toContain('shadow-key')
  expect(cls).toContain('rounded-lg') // --radius-lg es 9999px: píldora
  expect(cls).toContain('motion-reduce:enabled:active:translate-y-0')
  expect(cls).not.toMatch(/(^| )transition( |$)/)
})

test('un botón con atajo lo anuncia con aria-keyshortcuts y la tecla visible es decorativa', () => {
  render(<Button shortcut="C">Cotizar</Button>)
  const button = screen.getByRole('button', { name: 'Cotizar' })
  expect(button).toHaveAttribute('aria-keyshortcuts', 'C')
  expect(button.querySelector('kbd')).toHaveAttribute('aria-hidden', 'true')
})

test('la tecla visible solo aparece en escritorio con mouse', () => {
  render(<Kbd>/</Kbd>)
  const kbd = screen.getByText('/')
  expect(kbd.className).toContain('hidden')
  expect(kbd.className).toContain('pointer-fine:lg:inline-flex')
})

test('un botón con ícono lo muestra en un círculo amarillo decorativo', () => {
  render(<Button icon="quote">Cotizar</Button>)
  const dot = screen.getByRole('button', { name: 'Cotizar' }).querySelector('span[aria-hidden="true"]')
  expect(dot?.className).toContain('bg-accent')
  expect(dot?.className).toContain('rounded-full')
})

test('las tarjetas son una lista y las cifras usan cifras tabulares', () => {
  render(
    <Cells label="Accesos">
      <li>
        Total <Num>$65.200</Num>
      </li>
    </Cells>,
  )
  expect(screen.getByRole('list', { name: 'Accesos' })).toHaveClass('cells')
  expect(screen.getByText('$65.200')).toHaveClass('num')
})

function Probe({ onFire }: { onFire: () => void }) {
  useShortcut('c', onFire)
  return <input aria-label="campo" />
}

test('el atajo actúa con la tecla sola y no mientras se escribe ni con Ctrl', () => {
  const fire = vi.fn()
  render(<Probe onFire={fire} />)
  fireEvent.keyDown(window, { key: 'c' })
  expect(fire).toHaveBeenCalledTimes(1)
  fireEvent.keyDown(window, { key: 'c', ctrlKey: true })
  fireEvent.keyDown(screen.getByLabelText('campo'), { key: 'c' })
  fireEvent.keyDown(window, { key: 'C', repeat: true })
  expect(fire).toHaveBeenCalledTimes(1)
  expect(isTyping(screen.getByLabelText('campo'))).toBe(true)
})

test('la fuente es Urbanist autoalojada, sin CDN, y reemplaza a IBM Plex', () => {
  const fonts = read('fonts.css')
  expect(fonts).toContain('@fontsource-variable/urbanist')
  expect(fonts).not.toMatch(/ibm-plex/i)
  expect(fonts).not.toMatch(/https?:\/\//)
  const css = read('index.css')
  expect(css).toContain("--font-sans: 'Urbanist Variable'")
  expect(css).toContain("--font-display: 'Urbanist Variable'")
  expect(css).toContain('--radius-lg: 9999px')
})

test('el plato sin foto se dibuja y es decorativo', () => {
  const { container } = render(<Plate src={null} className="w-40" />)
  const plate = container.firstElementChild as HTMLElement
  expect(plate).toHaveAttribute('aria-hidden', 'true')
  expect(plate.querySelector('svg')).not.toBeNull()
  expect(plate.querySelector('img')).toBeNull()
})

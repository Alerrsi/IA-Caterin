/** Estética "plano de cocina" (T16, ADR-010): botón tecla, atajos, celdas, cifras y fuentes. */
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { fireEvent, render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import { Button, Cells, Kbd, Num } from './components/ui'
import { isTyping, useShortcut } from './shortcuts'

const read = (f: string) => readFileSync(resolve(__dirname, f), 'utf8')

test('el botón principal mantiene 48 px, foco visible, borde de tecla y respeta reducir movimiento', () => {
  render(<Button>Cotizar</Button>)
  const cls = screen.getByRole('button', { name: 'Cotizar' }).className
  expect(cls).toContain('min-h-12')
  expect(cls).toContain('focus-visible:ring-4')
  expect(cls).toContain('shadow-key')
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

test('las celdas son una lista y las cifras usan la monoespaciada', () => {
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

test('las fuentes son IBM Plex autoalojadas, sin CDN', () => {
  const fonts = read('fonts.css')
  expect(fonts).toContain('@fontsource/ibm-plex-serif')
  expect(fonts).toContain('@fontsource/ibm-plex-mono')
  expect(fonts).toContain('@fontsource-variable/ibm-plex-sans')
  expect(fonts).not.toMatch(/https?:\/\//)
  // Los @import deben ir antes de cualquier otra regla: si no, el navegador los ignora.
  expect(fonts.indexOf('@import')).toBeLessThan(fonts.indexOf('@font-face'))
  const css = read('index.css')
  expect(css).toContain("--font-mono: 'IBM Plex Mono'")
  expect(css).toContain("--font-display: 'IBM Plex Serif'")
})

/**
 * Contraste AA de los pares texto/fondo del tema (T14, T21). Lee los tokens de `src/index.css`, que escribe
 * `scripts/theme.mjs`: si se cambia un color y un par baja de 4.5:1, esta prueba falla.
 */
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, test } from 'vitest'

const css = readFileSync(resolve(__dirname, 'index.css'), 'utf8')
const tokens = Object.fromEntries([...css.matchAll(/--color-([a-z-]+):\s*(#[0-9a-f]{6})/gi)].map((m) => [m[1], m[2]]))

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

export function contrast(a: string, b: string): number {
  const [x, y] = [luminance(a), luminance(b)].sort((m, n) => n - m)
  return (x + 0.05) / (y + 0.05)
}

const SURFACES = [
  'surface',
  'surface-container-lowest',
  'surface-container-low',
  'surface-container',
  'surface-container-high',
  'surface-container-highest',
]

// [texto, fondo]: los pares que usa la app (texto normal, mínimo 4.5:1).
const PAIRS: [string, string][] = [
  ...['primary', 'secondary', 'tertiary', 'error', 'brand'].map((r): [string, string] => [`on-${r}`, r]),
  ...['primary', 'secondary', 'tertiary', 'error', 'warning', 'success', 'info'].map((r): [string, string] => [
    `on-${r}-container`,
    `${r}-container`,
  ]),
  ...SURFACES.flatMap((s): [string, string][] => [
    ['on-surface', s],
    ['on-surface-variant', s],
    ['primary', s], // enlaces y botones de texto
    ['brand', s], // logotipo
  ]),
  ...['error', 'warning', 'info', 'success'].map((r): [string, string] => [r, 'surface-container-lowest']),
  ['inverse-on-surface', 'inverse-surface'],
  // T21 (ADR-013): el amarillo solo es fondo, con texto negro; el panel oscuro lleva texto claro.
  ['on-accent', 'accent'],
  ['on-accent', 'accent-soft'],
  ['on-panel', 'panel'],
  ['on-panel-variant', 'panel'],
  ['tertiary', 'surface-container-lowest'],
]

describe('tema', () => {
  test('tiene todos los roles que usa la app', () => {
    for (const [fg, bg] of PAIRS) {
      expect(tokens[fg], fg).toMatch(/^#/)
      expect(tokens[bg], bg).toMatch(/^#/)
    }
  })

  test.each(PAIRS)('%s sobre %s cumple AA (4.5:1)', (fg, bg) => {
    expect(contrast(tokens[fg], tokens[bg])).toBeGreaterThanOrEqual(4.5)
  })

  test('el amarillo no sirve como texto sobre blanco: por eso solo es fondo (ADR-013)', () => {
    expect(contrast(tokens.accent, tokens['surface-container-lowest'])).toBeLessThan(3)
  })

  test('el contorno de los campos se distingue del fondo (3:1, WCAG 1.4.11)', () => {
    expect(contrast(tokens.outline, tokens['surface-container-lowest'])).toBeGreaterThanOrEqual(3)
  })
})

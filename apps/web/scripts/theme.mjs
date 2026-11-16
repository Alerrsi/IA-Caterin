#!/usr/bin/env node
/**
 * Tokens de color de Cáterin (T21, ADR-013) escritos en `src/index.css`, entre los marcadores `theme:start` y
 * `theme:end`. La paleta sale de la imagen de referencia que eligió el usuario: blanco limpio, tinta casi negra,
 * un panel oscuro y un acento amarillo cálido. Ya no se genera desde una semilla MD3 (ADR-008, reemplazado): se
 * declara a mano y `src/theme.test.ts` verifica AA en cada par texto/fondo.
 *
 *   npm run theme            # escribe src/index.css
 *   npm run theme -- --check # falla si src/index.css no coincide (lo usa CI)
 *
 * Los nombres de los roles se mantienen (primary, surface-container, on-surface-variant…) para no tocar cada
 * componente. Reglas de uso:
 * - primary: tinta casi negra; botón principal, enlaces y selección.
 * - accent: amarillo de la referencia, SOLO como fondo (círculo del ícono del botón, chips, detalles). Su texto es
 *   `on-accent` (negro). Nunca amarillo como texto sobre blanco (1,4:1).
 * - tertiary: ámbar oscuro para íconos o detalles cálidos sobre blanco (pasa AA).
 * - panel: el panel oscuro con dibujos de comida (portadas); su texto es `on-panel`.
 */
import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

export const INK = '#1a1a1a'
export const ACCENT = '#ffd45c'

const PALETTE = {
  primary: INK,
  'on-primary': '#ffffff',
  'primary-container': '#fff4cf',
  'on-primary-container': '#2b2100',
  secondary: '#4f4c47',
  'on-secondary': '#ffffff',
  'secondary-container': '#f1efea',
  'on-secondary-container': '#1a1a1a',
  tertiary: '#7a5200',
  'on-tertiary': '#ffffff',
  'tertiary-container': '#ffe7a3',
  'on-tertiary-container': '#2b1d00',
  surface: '#ffffff',
  'surface-dim': '#e4e2dd',
  'surface-bright': '#ffffff',
  'surface-container-lowest': '#ffffff',
  'surface-container-low': '#f7f6f3',
  'surface-container': '#f1efea',
  'surface-container-high': '#ebe9e4',
  'surface-container-highest': '#e4e2dd',
  'on-surface': INK,
  'on-surface-variant': '#57544e',
  outline: '#85827b',
  'outline-variant': '#d9d6cf',
  'inverse-surface': '#1b1b1b',
  'inverse-on-surface': '#f7f6f3',
  'inverse-primary': ACCENT,
  error: '#b3261e',
  'on-error': '#ffffff',
  'error-container': '#fde2df',
  'on-error-container': '#5c0f0a',
  warning: '#7a5600',
  'warning-container': '#fff0c2',
  'on-warning-container': '#2b1f00',
  success: '#2e6b3a',
  'success-container': '#dcf1df',
  'on-success-container': '#0b2611',
  info: '#2f5f8a',
  'info-container': '#dceaf7',
  'on-info-container': '#08223a',
  // Líneas finas de divisores y tarjetas, y el borde del botón (ya sin efecto tecla; se conserva el nombre).
  hairline: '#ecebe7',
  'primary-edge': '#000000',
  // Marca: tinta para el logo y la barra del sistema; el "vapor" de la cloche en amarillo.
  brand: INK,
  'on-brand': '#ffffff',
  'brand-steam': ACCENT,
  // Acento amarillo de la referencia (solo fondo) y el panel oscuro de las portadas.
  accent: ACCENT,
  'on-accent': INK,
  'accent-soft': '#fff4cf',
  panel: '#1b1b1b',
  'on-panel': '#f7f6f3',
  'on-panel-variant': '#c9c6bf',
}

const here = dirname(fileURLToPath(import.meta.url))
const CSS = resolve(here, '../src/index.css')
const START = '/* theme:start (generado por scripts/theme.mjs; no editar a mano) */'
const END = '/* theme:end */'

export function tokens() {
  return { ...PALETTE }
}

export function block() {
  const lines = Object.entries(tokens()).map(([k, v]) => `  --color-${k}: ${v};`)
  return [START, `  /* Tinta ${INK}, acento ${ACCENT} (ADR-013). */`, ...lines, `  ${END}`].join('\n')
}

function main() {
  const css = readFileSync(CSS, 'utf8')
  const a = css.indexOf(START)
  const b = css.indexOf(END)
  if (a < 0 || b < 0) throw new Error(`Faltan los marcadores del tema en ${CSS}`)
  const next = css.slice(0, a) + block() + css.slice(b + END.length)
  if (process.argv.includes('--check')) {
    if (next !== css) {
      console.error('src/index.css no coincide con scripts/theme.mjs: corre `npm run theme`.')
      process.exit(1)
    }
    console.log('Tema al día.')
    return
  }
  writeFileSync(CSS, next)
  console.log('Tema escrito en src/index.css (ADR-013).')
}

if (process.argv[1] === fileURLToPath(import.meta.url)) main()

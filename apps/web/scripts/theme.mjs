#!/usr/bin/env node
/**
 * Genera los tokens de color MD3 de Cáterin desde un color semilla (T14, ADR-008) y los escribe en `src/index.css`,
 * entre los marcadores `theme:start` y `theme:end`. Los colores no se escriben a mano: se cambia la semilla y se vuelve
 * a correr.
 *
 *   npm run theme            # escribe src/index.css
 *   npm run theme -- --check # falla si src/index.css no coincide con lo generado (lo usa CI)
 *
 * Semilla: maqui, la baya nativa de La Araucanía. Las paletas tonales se arman a mano (tono y croma) y los roles los
 * calcula `DynamicScheme` de MD3, con los mismos tonos que el esquema "tonal spot", en modo claro:
 * - primaria: tono de la semilla con croma 48 (más viva que tonal spot, que la apaga a 36);
 * - secundaria: mismo tono con croma 16 (recesiva, como manda MD3);
 * - terciaria: verde araucaria, el acento que contrasta;
 * - neutros: tono de la semilla con croma 2 y 5, casi sin tinte (ni gris frío ni crema).
 * Los estados que MD3 no define (aviso, éxito, información) parten de un tono fijo, se armonizan con la semilla y se
 * limitan de croma para que los contenedores no queden chillones.
 *
 * Se usa la versión 0.3.0 de material-color-utilities: la 0.4.0 publica ESM sin extensiones y no corre en Node.
 */
import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { argbFromHex, Blend, DynamicScheme, hexFromArgb, Hct, TonalPalette } from '@material/material-color-utilities'

export const SEED = '#6d2a57' // maqui
const ARAUCARIA = '#3f5f3a'
const STATES = { warning: '#8a6100', success: '#2e7d32', info: '#2f6290' }
const STATE_CHROMA = 32
const TONAL_SPOT = 2 // Variant.TONAL_SPOT (el enum no se exporta en 0.3.0)

const here = dirname(fileURLToPath(import.meta.url))
const CSS = resolve(here, '../src/index.css')
const START = '/* theme:start (generado por scripts/theme.mjs; no editar a mano) */'
const END = '/* theme:end */'

const hex = (argb) => hexFromArgb(argb)

export function tokens(seed = SEED) {
  const src = Hct.fromInt(argbFromHex(seed))
  const palette = (hue, chroma) => TonalPalette.fromHueAndChroma(hue, chroma)
  const s = new DynamicScheme({
    sourceColorArgb: src.toInt(),
    variant: TONAL_SPOT,
    contrastLevel: 0,
    isDark: false,
    primaryPalette: palette(src.hue, 48),
    secondaryPalette: palette(src.hue, 16),
    tertiaryPalette: palette(Hct.fromInt(argbFromHex(ARAUCARIA)).hue, 30),
    neutralPalette: palette(src.hue, 2),
    neutralVariantPalette: palette(src.hue, 5),
  })
  const roles = {
    primary: s.primary,
    'on-primary': s.onPrimary,
    'primary-container': s.primaryContainer,
    'on-primary-container': s.onPrimaryContainer,
    secondary: s.secondary,
    'on-secondary': s.onSecondary,
    'secondary-container': s.secondaryContainer,
    'on-secondary-container': s.onSecondaryContainer,
    tertiary: s.tertiary,
    'on-tertiary': s.onTertiary,
    'tertiary-container': s.tertiaryContainer,
    'on-tertiary-container': s.onTertiaryContainer,
    surface: s.surface,
    'surface-dim': s.surfaceDim,
    'surface-bright': s.surfaceBright,
    'surface-container-lowest': s.surfaceContainerLowest,
    'surface-container-low': s.surfaceContainerLow,
    'surface-container': s.surfaceContainer,
    'surface-container-high': s.surfaceContainerHigh,
    'surface-container-highest': s.surfaceContainerHighest,
    'on-surface': s.onSurface,
    'on-surface-variant': s.onSurfaceVariant,
    outline: s.outline,
    'outline-variant': s.outlineVariant,
    'inverse-surface': s.inverseSurface,
    'inverse-on-surface': s.inverseOnSurface,
    'inverse-primary': s.inversePrimary,
    error: s.error,
    'on-error': s.onError,
    'error-container': s.errorContainer,
    'on-error-container': s.onErrorContainer,
  }
  const out = Object.fromEntries(Object.entries(roles).map(([k, v]) => [k, hex(v)]))
  for (const [name, base] of Object.entries(STATES)) {
    const h = Hct.fromInt(Blend.harmonize(argbFromHex(base), argbFromHex(seed)))
    const p = palette(h.hue, Math.min(h.chroma, STATE_CHROMA))
    out[name] = hex(p.tone(40))
    out[`${name}-container`] = hex(p.tone(90))
    out[`on-${name}-container`] = hex(p.tone(10))
  }
  // Marca: el maqui puro de la semilla (logo, barra del sistema y panel del login) y sus tonos claros.
  out.brand = seed.toLowerCase()
  out['on-brand'] = hex(s.surface)
  out['brand-steam'] = hex(s.primaryContainer)
  return out
}

export function block(seed = SEED) {
  const lines = Object.entries(tokens(seed)).map(([k, v]) => `  --color-${k}: ${v};`)
  return [START, `  /* Semilla ${seed} (maqui), terciaria ${ARAUCARIA} (araucaria). */`, ...lines, `  ${END}`].join('\n')
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
  console.log(`Tema escrito en src/index.css desde ${SEED}.`)
}

if (process.argv[1] === fileURLToPath(import.meta.url)) main()

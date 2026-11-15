#!/usr/bin/env node
/**
 * Genera los tokens de color MD3 de Cáterin desde un color semilla (T14, ADR-008) y los escribe en `src/index.css`,
 * entre los marcadores `theme:start` y `theme:end`. Los colores no se escriben a mano: se cambia la semilla y se vuelve
 * a correr.
 *
 *   npm run theme            # escribe src/index.css
 *   npm run theme -- --check # falla si src/index.css no coincide con lo generado (lo usa CI)
 *
 * Semilla: laurel, el verde profundo de las hierbas de cocina (ADR-008, revisión del 15-nov-2026). Dirección
 * "cocina profesional ordenada": una sola tinta de marca, neutros casi blancos y un acento cobre (las ollas) que se usa
 * poco. Las paletas tonales se arman a mano (tono y croma) y los roles los calcula `DynamicScheme`, en modo claro:
 * - primaria: tono de la semilla con croma 30 (botones y enlaces);
 * - contenedores de la primaria: mismo tono con croma 14, para que los fondos suaves no queden menta chillón;
 * - secundaria: mismo tono con croma 10 (recesiva);
 * - terciaria: cobre, el único acento cálido;
 * - neutros: tono de la semilla con croma 2 y 4: superficies casi blancas, sin crema ni gris azulado.
 * Los estados (aviso, éxito, información) parten de un tono fijo, se armonizan con la semilla y se limitan de croma.
 * Los nombres de los tokens siguen los roles de Material Design 3 por compatibilidad con los componentes; la guía de
 * diseño ya no es MD3 sino `interface-design` (ver `.claude/skills/SOURCES.md`).
 *
 * Se usa la versión 0.3.0 de material-color-utilities: la 0.4.0 publica ESM sin extensiones y no corre en Node.
 */
import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { argbFromHex, Blend, DynamicScheme, hexFromArgb, Hct, TonalPalette } from '@material/material-color-utilities'

export const SEED = '#1f4d3f' // laurel
const COBRE = '#a0522d'
const STATES = { warning: '#8a6100', success: '#2e7d32', info: '#2f6290' }
const STATE_CHROMA = 22
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
    primaryPalette: palette(src.hue, 30),
    secondaryPalette: palette(src.hue, 10),
    tertiaryPalette: palette(Hct.fromInt(argbFromHex(COBRE)).hue, 40),
    neutralPalette: palette(src.hue, 2),
    neutralVariantPalette: palette(src.hue, 4),
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
  // Contenedores de la primaria más sobrios que MD3 (mismo tono 90/30, menos croma).
  const soft = palette(src.hue, 14)
  out['primary-container'] = hex(soft.tone(90))
  out['on-primary-container'] = hex(soft.tone(30))
  for (const [name, base] of Object.entries(STATES)) {
    const h = Hct.fromInt(Blend.harmonize(argbFromHex(base), argbFromHex(seed)))
    const p = palette(h.hue, Math.min(h.chroma, STATE_CHROMA))
    out[name] = hex(p.tone(40))
    out[`${name}-container`] = hex(p.tone(90))
    out[`on-${name}-container`] = hex(p.tone(10))
  }
  // Plano de cocina (T16, ADR-010): línea fina para rieles, celdas y divisores (entre outline-variant y la superficie),
  // y el borde inferior de la "tecla" del botón principal (un tono más oscuro que primary).
  out.hairline = hex(palette(src.hue, 4).tone(88))
  out['primary-edge'] = hex(palette(src.hue, 30).tone(25))
  // Marca: el laurel puro de la semilla (logo, barra del sistema y panel del login) y el vapor cobre claro.
  out.brand = seed.toLowerCase()
  out['on-brand'] = hex(s.surface)
  out['brand-steam'] = hex(s.tertiaryContainer)
  return out
}

export function block(seed = SEED) {
  const lines = Object.entries(tokens(seed)).map(([k, v]) => `  --color-${k}: ${v};`)
  return [START, `  /* Semilla ${seed} (laurel), terciaria ${COBRE} (cobre). */`, ...lines, `  ${END}`].join('\n')
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

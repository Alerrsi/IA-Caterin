#!/usr/bin/env node
/**
 * PNG de la marca desde los SVG de `public/brand/` (T14): íconos de la PWA, apple-touch-icon y el isotipo del PDF.
 * Usa el Chromium de Playwright (ya es dependencia de las pruebas), así no se agrega una librería nativa.
 *
 *   npm run icons      (PW_CHROMIUM=/ruta/al/chromium si no está en /usr/bin/chromium)
 */
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from '@playwright/test'

const web = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const brand = (f) => readFileSync(resolve(web, 'public/brand', f), 'utf8')

const targets = [
  // [svg, tamaño, salida, fondo transparente]
  ['isotipo.svg', 192, 'public/pwa-192.png', true],
  ['isotipo.svg', 512, 'public/pwa-512.png', true],
  ['isotipo-maskable.svg', 512, 'public/pwa-maskable-512.png', false],
  ['isotipo-maskable.svg', 180, 'public/apple-touch-icon.png', false], // iOS redondea las esquinas
  ['isotipo.svg', 64, 'public/favicon-64.png', true],
  ['isotipo-mono.svg', 256, '../api/app/assets/caterin-isotipo-mono.png', true],
]

const browser = await chromium.launch({ executablePath: process.env.PW_CHROMIUM ?? '/usr/bin/chromium' })
const page = await browser.newPage()
for (const [svg, size, out, transparent] of targets) {
  await page.setViewportSize({ width: size, height: size })
  const markup = brand(svg).replace('<svg ', `<svg width="${size}" height="${size}" `)
  await page.setContent(`<html><body style="margin:0;background:transparent">${markup}</body></html>`)
  await page.screenshot({ path: resolve(web, out), omitBackground: transparent, clip: { x: 0, y: 0, width: size, height: size } })
  console.log(`${out} (${size}px)`)
}
await browser.close()

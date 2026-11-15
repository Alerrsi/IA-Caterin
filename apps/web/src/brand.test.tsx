/** Marca (T14): logo accesible, color de la barra coherente, íconos de la PWA y tema generado al día. */
import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import { AuthLayout, Logo } from './components/Logo'

const web = resolve(__dirname, '..')
const read = (f: string) => readFileSync(resolve(web, f), 'utf8')

test('el logo dice "Cáterin" como texto y el dibujo es decorativo', () => {
  const { container } = render(<Logo />)
  expect(screen.getByText('Cáterin')).toBeInTheDocument()
  expect(container.querySelector('svg')).toHaveAttribute('aria-hidden', 'true')
})

test('en el login la marca es el título de la pantalla', () => {
  render(
    <AuthLayout titleAsHeading>
      <p>formulario</p>
    </AuthLayout>,
  )
  expect(screen.getByRole('heading', { level: 1, name: 'Cáterin' })).toBeInTheDocument()
})

test('theme-color es el mismo en index.html y en el manifiesto', () => {
  const html = read('index.html').match(/name="theme-color" content="(#[0-9a-f]{6})"/i)?.[1]
  const manifest = read('vite.config.ts').match(/THEME_COLOR = '(#[0-9a-f]{6})'/i)?.[1]
  expect(html).toBeDefined()
  expect(html).toBe(manifest)
  expect(read('src/index.css')).toContain(`--color-brand: ${html};`)
})

test('la PWA declara PNG "any" y un ícono maskable aparte, y los archivos existen', () => {
  const config = read('vite.config.ts')
  for (const png of ['pwa-192.png', 'pwa-512.png', 'pwa-maskable-512.png', 'apple-touch-icon.png']) {
    expect(existsSync(resolve(web, 'public', png)), png).toBe(true)
  }
  expect(config).toMatch(/pwa-maskable-512\.png'.*purpose: 'maskable'/)
  expect(config).not.toContain("'any maskable'")
  expect(config).toMatch(/globPatterns:.*woff2/)
  expect(existsSync(resolve(web, '../api/app/assets/caterin-isotipo-mono.png'))).toBe(true)
})

test('index.css coincide con lo que genera scripts/theme.mjs', () => {
  expect(() => execFileSync('node', ['scripts/theme.mjs', '--check'], { cwd: web, stdio: 'pipe' })).not.toThrow()
})

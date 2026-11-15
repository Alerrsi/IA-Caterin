import type { ReactNode } from 'react'
import { t } from '../i18n'

/**
 * Marca de Cáterin (T14, ADR-008): una cloche con vapor, "comida caliente lista para servir". Es el mismo dibujo de
 * `public/brand/*.svg` (los genera `scripts/brand.py`), en línea para que funcione sin red y tome los colores del tema.
 */
function Glyph() {
  return (
    <g transform="translate(0 20)">
      <path
        d="M216 164c-14-12 14-24 0-36s14-24 0-36M296 164c-14-12 14-24 0-36s14-24 0-36"
        fill="none"
        stroke="var(--color-brand-steam)"
        strokeWidth="18"
        strokeLinecap="round"
      />
      <circle cx="256" cy="190" r="20" fill="var(--color-on-brand)" />
      <path d="M126 336a130 130 0 0 1 260 0z" fill="var(--color-on-brand)" />
      <rect x="96" y="350" width="320" height="30" rx="15" fill="var(--color-on-brand)" />
      <path d="M182 304a92 92 0 0 1 52-62" fill="none" stroke="var(--color-brand)" strokeWidth="16" strokeLinecap="round" />
    </g>
  )
}

/** Isotipo. Decorativo por defecto: el nombre "Cáterin" va siempre al lado como texto. */
export function Isotipo({ className = 'h-10 w-10', framed = true }: { className?: string; framed?: boolean }) {
  return (
    <svg viewBox="0 0 512 512" className={className} aria-hidden="true" focusable="false">
      {framed && <rect width="512" height="512" rx="116" fill="var(--color-brand)" />}
      <Glyph />
    </svg>
  )
}

/** Logo horizontal: isotipo + la palabra en la tipografía de la marca (texto real, legible por lectores de pantalla). */
export function Logo({ size = 'md', className = '' }: { size?: 'sm' | 'md'; className?: string }) {
  const sm = size === 'sm'
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <Isotipo className={sm ? 'h-8 w-8' : 'h-10 w-10'} />
      <span className={`font-display font-semibold tracking-tight text-brand ${sm ? 'text-xl' : 'text-2xl'}`}>
        {t.appName}
      </span>
    </span>
  )
}

/**
 * Marco de las pantallas sin sesión (entrar, crear cuenta, registro de cliente). El único momento "fuerte" de la marca:
 * un panel maqui con la cloche grande; todo lo demás queda sobrio. En el celular el panel va arriba y el formulario lo
 * monta encima; desde 1024 px, a la izquierda.
 * `titleAsHeading`: en el login la marca es el título de la pantalla (h1); en los registros el título es el del formulario.
 */
export function AuthLayout({ children, titleAsHeading = false }: { children: ReactNode; titleAsHeading?: boolean }) {
  const Title = titleAsHeading ? 'h1' : 'p'
  return (
    <main className="min-h-dvh bg-surface-container lg:grid lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
      <header className="bg-brand px-6 pb-16 pt-10 text-on-brand lg:flex lg:flex-col lg:justify-center lg:px-16 lg:pb-10">
        <div className="mx-auto flex max-w-md items-center gap-4 lg:mx-0 lg:block">
          <Isotipo framed={false} className="h-20 w-20 shrink-0 lg:-ml-4 lg:h-40 lg:w-40" />
          <div>
            <Title className="font-display text-5xl font-semibold tracking-tight lg:mt-2 lg:text-7xl">{t.appName}</Title>
            <p className="mt-1 text-lg text-on-brand/90 lg:mt-4 lg:max-w-sm lg:text-2xl">{t.tagline}</p>
          </div>
        </div>
      </header>
      <div className="-mt-8 px-4 pb-10 lg:mt-0 lg:flex lg:items-center lg:justify-center lg:py-10">
        <div className="mx-auto w-full max-w-md rounded-3xl border border-outline-variant bg-surface-container-lowest p-6 md:p-10">
          {children}
        </div>
      </div>
    </main>
  )
}

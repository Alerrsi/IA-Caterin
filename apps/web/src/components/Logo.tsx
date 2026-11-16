import type { ReactNode } from 'react'
import { t } from '../i18n'
import { Coupon, FOTOS, Floater, FoodPanel, Plate, Squiggle } from './Food'
import { Pill } from './ui'

/**
 * Marca de Cáterin (T14; recoloreada en T21, ADR-013): una cloche con vapor, "comida caliente lista para servir", blanca
 * sobre tinta y con el vapor amarillo. Es el mismo dibujo de `public/brand/*.svg` (los genera `scripts/brand.py`), en
 * línea para que funcione sin red y tome los colores del tema.
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
      {framed && <rect width="512" height="512" rx="120" fill="var(--color-brand)" />}
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
      <span className={`font-display font-extrabold tracking-tight text-brand ${sm ? 'text-xl' : 'text-2xl'}`}>
        {t.appName}
      </span>
    </span>
  )
}

/**
 * Marco de las pantallas sin sesión (entrar, crear cuenta, registro de cliente), la pantalla más parecida a la imagen
 * de referencia (T21, ADR-013): a un lado, la marca, un título grande en dos pesos y el formulario; al otro, el panel
 * oscuro en diagonal con dibujos de comida, un plato enorme que se sale del panel, ingredientes flotando y una tarjeta
 * punteada tipo cupón. En el celular el panel va arriba y el formulario debajo.
 * `titleAsHeading`: en el login la marca es el título de la pantalla (h1); en los registros el título es el del formulario.
 */
export function AuthLayout({ children, titleAsHeading = false }: { children: ReactNode; titleAsHeading?: boolean }) {
  const Title = titleAsHeading ? 'h1' : 'p'
  const [lead, rest] = t.taglineParts
  return (
    <main className="min-h-dvh overflow-x-clip bg-surface-container-lowest">
      <div className="mx-auto grid max-w-7xl lg:min-h-dvh lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        <div className="relative z-10 order-2 px-5 pb-12 lg:order-1 lg:flex lg:flex-col lg:justify-center lg:py-12 lg:pl-12 lg:pr-6">
          <div className="flex items-center gap-3">
            <Isotipo className="h-11 w-11" />
            <Title className="font-display text-3xl font-extrabold tracking-tight text-on-surface">{t.appName}</Title>
          </div>
          <div className="mt-6 flex gap-4 lg:mt-10">
            <Squiggle className="mt-3 hidden h-6 w-12 shrink-0 text-on-surface-variant md:block" />
            <p className="text-[2.1rem] leading-[2.5rem] tracking-tight text-on-surface md:text-5xl md:leading-[3.4rem]">
              <span className="block font-normal">{lead}</span>
              <span className="block font-extrabold">{rest}</span>
            </p>
          </div>
          <div className="mt-8 w-full max-w-md rounded-3xl bg-surface-container-lowest p-6 shadow-soft ring-1 ring-black/5 md:p-8 lg:ml-16">
            {children}
          </div>
        </div>

        <FoodPanel className="order-1 h-[330px] sm:h-[400px] lg:order-2 lg:h-auto">
          <div className="relative h-[330px] sm:h-[400px] lg:h-full lg:min-h-dvh">
            <Floater kind="tomato" className="left-[8%] top-[10%] h-12 w-12 lg:left-[-2%] lg:top-[26%] lg:h-16 lg:w-16" />
            <Floater kind="basil" className="right-[10%] top-[8%] h-14 w-14 rotate-12 lg:right-[18%] lg:top-[12%] lg:h-20 lg:w-20" />
            <Floater kind="lemon" className="bottom-[14%] left-[14%] h-10 w-10 lg:bottom-[38%] lg:left-[6%] lg:h-14 lg:w-14" />
            <Plate className="absolute left-1/2 top-[52%] w-[230px] -translate-x-1/2 -translate-y-1/2 sm:w-[290px] lg:left-[30%] lg:top-[40%] lg:w-[min(480px,38vw)]" />
            <Floater kind="chili" className="bottom-[22%] right-[12%] h-12 w-12 -rotate-12 lg:bottom-[42%] lg:right-[10%] lg:h-16 lg:w-16" />
            <Coupon dark title={t.authCoupon.title} className="absolute bottom-10 right-8 hidden w-[min(380px,32vw)] lg:block">
              <div className="flex items-center gap-4">
                <Plate src={FOTOS.plate2} className="w-16 shrink-0" />
                <p className="min-w-0 flex-1 font-semibold leading-snug">{t.authCoupon.body}</p>
                <Pill>{t.authCoupon.pill}</Pill>
              </div>
            </Coupon>
          </div>
        </FoodPanel>
      </div>
    </main>
  )
}

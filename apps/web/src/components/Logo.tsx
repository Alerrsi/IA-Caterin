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
 * punteada tipo cupón.
 *
 * **Sin scroll en la primera vista** (requisito de T21): en el celular el formulario manda; el panel es una franja de
 * 18 % del alto (`dvh`) con el plato asomándose, recortado por la diagonal, y en pantallas bajas (`short`) se oculta el
 * lema. En escritorio todo cabe en `100dvh`. Se usa `min-h-dvh` (no un alto fijo): con zoom o con el teclado abierto la
 * página puede crecer y desplazarse, nunca recortar.
 * `titleAsHeading`: en el login la marca es el título de la pantalla (h1); en los registros el título es el del formulario.
 * `compact`: sin el lema en el celular (formularios largos, como crear cuenta).
 */
export function AuthLayout({
  children,
  titleAsHeading = false,
  compact = false,
}: {
  children: ReactNode
  titleAsHeading?: boolean
  compact?: boolean
}) {
  const Title = titleAsHeading ? 'h1' : 'p'
  const [lead, rest] = t.taglineParts
  return (
    <main className="flex min-h-dvh flex-col overflow-x-clip bg-surface-container-lowest lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
      <div className="relative z-10 order-2 flex flex-1 flex-col justify-center px-5 py-4 sm:px-8 lg:order-1 lg:py-6 lg:pl-12 lg:pr-6">
        <div className="mx-auto w-full max-w-md lg:mx-0 lg:max-w-none">
          <div className="flex items-center gap-3">
            <Isotipo className="h-9 w-9 lg:h-11 lg:w-11" />
            <Title className="font-display text-2xl font-extrabold tracking-tight text-on-surface lg:text-3xl">{t.appName}</Title>
          </div>
          <div className={`mt-3 gap-4 lg:mt-6 lg:flex ${compact ? 'max-lg:hidden' : 'max-lg:short:hidden'}`}>
            <Squiggle className="mt-3 hidden h-6 w-12 shrink-0 text-on-surface-variant lg:block" />
            <p className="text-[1.65rem] leading-[1.95rem] tracking-tight text-on-surface sm:text-4xl sm:leading-[2.6rem] lg:text-[2.6rem] lg:leading-[3rem] lg:short:text-4xl lg:short:leading-[2.6rem]">
              <span className="block font-normal">{lead}</span>
              <span className="block font-extrabold">{rest}</span>
            </p>
          </div>
          <div className="mt-4 w-full max-w-md lg:ml-16 lg:mt-6 lg:rounded-3xl lg:bg-surface-container-lowest lg:p-7 lg:shadow-soft lg:ring-1 lg:ring-black/5 lg:short:mt-5 lg:short:p-6">
            {children}
          </div>
        </div>
      </div>

      <FoodPanel className="order-1 h-[clamp(88px,18dvh,200px)] shrink-0 lg:order-2 lg:h-auto">
        {/* En el celular el plato se asoma, recortado por la misma diagonal del panel. */}
        <div className="relative h-[clamp(88px,18dvh,200px)] [clip-path:polygon(0_0,100%_0,100%_86%,0_100%)] lg:h-full lg:min-h-dvh lg:[clip-path:none]">
          <Plate className="absolute left-1/2 top-[14%] w-[min(58vw,250px)] -translate-x-1/2 lg:left-[30%] lg:top-[40%] lg:w-[min(460px,36vw,58dvh)] lg:-translate-y-1/2" />
          <Floater kind="tomato" className="left-[7%] top-[18%] h-9 w-9 lg:left-[-2%] lg:top-[26%] lg:h-16 lg:w-16" />
          <Floater kind="basil" className="right-[8%] top-[12%] h-10 w-10 rotate-12 lg:right-[18%] lg:top-[12%] lg:h-20 lg:w-20" />
          <Floater kind="lemon" className="hidden lg:bottom-[38%] lg:left-[6%] lg:block lg:h-14 lg:w-14" />
          <Floater kind="chili" className="hidden lg:bottom-[42%] lg:right-[10%] lg:block lg:h-16 lg:w-16 lg:-rotate-12" />
          <Coupon dark title={t.authCoupon.title} className="absolute bottom-8 right-8 hidden w-[min(380px,32vw)] lg:block lg:short:hidden">
            <div className="flex items-center gap-4">
              <Plate src={FOTOS.plate2} className="w-16 shrink-0" />
              <p className="min-w-0 flex-1 font-semibold leading-snug">{t.authCoupon.body}</p>
              <Pill>{t.authCoupon.pill}</Pill>
            </div>
          </Coupon>
        </div>
      </FoodPanel>
    </main>
  )
}

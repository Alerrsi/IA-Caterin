/**
 * Piezas de la estética de la referencia (T21, ADR-013): el panel oscuro en diagonal con dibujos de comida, el plato
 * redondo enorme visto desde arriba, los ingredientes que "flotan" y la tarjeta punteada tipo cupón.
 *
 * Las fotos viven en `public/fotos/` (las trae otra tarea, con licencia libre). Si una foto no carga (todavía no está,
 * o no hay red y no quedó en caché), se dibuja un reemplazo vectorial para que la composición no se rompa.
 * Todo es decorativo (`aria-hidden`), salvo lo que el llamador marque.
 */
import { useState, type ReactNode } from 'react'

export const FOTOS = {
  hero: '/fotos/plato-hero.webp',
  plate2: '/fotos/plato-2.webp',
  plate3: '/fotos/plato-3.webp',
  basil: '/fotos/ingrediente-albahaca.webp',
  tomato: '/fotos/ingrediente-tomate.webp',
  lemon: '/fotos/ingrediente-limon.webp',
  chili: '/fotos/ingrediente-aji.webp',
} as const

/** Plato dibujado: borde blanco, fondo crema y tres empanadas (el reemplazo cuando no hay foto). */
function DrawnPlate() {
  return (
    <svg viewBox="0 0 200 200" className="h-full w-full" aria-hidden="true" focusable="false">
      <circle cx="100" cy="100" r="98" fill="#fbfaf7" />
      <circle cx="100" cy="100" r="80" fill="#f1ece2" />
      <circle cx="100" cy="100" r="80" fill="none" stroke="#e4dccd" strokeWidth="3" />
      {[0, 120, 240].map((r) => (
        <g key={r} transform={`rotate(${r} 100 100)`}>
          <path d="M76 80a24 19 0 0 1 48 0z" fill="#e2a65a" stroke="#c4843a" strokeWidth="2.5" strokeLinejoin="round" />
          {[82, 91, 100, 109, 118].map((x) => (
            <circle key={x} cx={x} cy="78" r="2" fill="#c4843a" />
          ))}
        </g>
      ))}
      <path d="M92 104q8-12 18 0q-10 12-18 0z" fill="#4f9d4f" />
    </svg>
  )
}

/** Plato redondo con sombra difusa. `src`: foto ya recortada en círculo (o cuadrada: se recorta igual). */
export function Plate({ src = FOTOS.hero, className = '' }: { src?: string | null; className?: string }) {
  const [failed, setFailed] = useState(!src)
  return (
    <div aria-hidden="true" className={`aspect-square rounded-full shadow-plate ${className}`}>
      {failed ? (
        <DrawnPlate />
      ) : (
        <img
          src={src ?? undefined}
          alt=""
          width={800}
          height={800}
          decoding="async"
          onError={() => setFailed(true)}
          className="h-full w-full rounded-full object-cover"
        />
      )}
    </div>
  )
}

type Ingredient = 'basil' | 'tomato' | 'lemon' | 'chili'

const DRAWN: Record<Ingredient, ReactNode> = {
  basil: <path d="M8 52Q10 14 52 8Q50 46 8 52ZM8 52 40 20" fill="#4f9d4f" stroke="#2f6b2f" strokeWidth="2.5" strokeLinecap="round" />,
  tomato: (
    <>
      <circle cx="30" cy="34" r="24" fill="#e2483d" />
      <circle cx="22" cy="26" r="6" fill="#ffffff" opacity=".35" />
      <path d="M30 12l4 6 7-2-4 6 6 4-8 1-5 6-1-7-7-1 6-4-3-6z" fill="#3f8a3f" />
    </>
  ),
  lemon: (
    <>
      <circle cx="30" cy="30" r="26" fill="#f2c94c" />
      <circle cx="30" cy="30" r="21" fill="#fbe7a0" />
      {[0, 60, 120, 180, 240, 300].map((r) => (
        <path key={r} d="M30 30V11" stroke="#f2c94c" strokeWidth="2.5" transform={`rotate(${r} 30 30)`} />
      ))}
    </>
  ),
  chili: <path d="M14 48q30-4 38-34l4 2q-6 34-42 36z" fill="#c8331f" stroke="#8f2014" strokeWidth="2" strokeLinejoin="round" />,
}

/** Ingrediente que "flota" alrededor del plato, con sombra suave. Si no hay foto, uno dibujado. */
export function Floater({ kind, className = '' }: { kind: Ingredient; className?: string }) {
  const [failed, setFailed] = useState(false)
  const src = { basil: FOTOS.basil, tomato: FOTOS.tomato, lemon: FOTOS.lemon, chili: FOTOS.chili }[kind]
  return (
    <span aria-hidden="true" className={`pointer-events-none absolute block drop-shadow-[0_14px_14px_rgb(0_0_0/0.28)] ${className}`}>
      {failed ? (
        <svg viewBox="0 0 60 60" className="h-full w-full" focusable="false">
          {DRAWN[kind]}
        </svg>
      ) : (
        <img src={src} alt="" decoding="async" onError={() => setFailed(true)} className="h-full w-full object-contain" />
      )}
    </span>
  )
}

/**
 * Panel oscuro con dibujos de comida y corte diagonal: en el celular el corte va abajo; desde `lg`, a la izquierda.
 * El contenido (plato, cupón) se dibuja encima y puede salirse del panel.
 */
export function FoodPanel({ className = '', children }: { className?: string; children?: ReactNode }) {
  return (
    <div className={`relative ${className}`}>
      <div
        aria-hidden="true"
        className="doodles absolute inset-0 bg-panel [clip-path:polygon(0_0,100%_0,100%_86%,0_100%)] lg:[clip-path:polygon(22%_0,100%_0,100%_100%,0_100%)]"
      />
      <div className="relative">{children}</div>
    </div>
  )
}

/** Tarjeta punteada tipo cupón (como "Discount coupon" de la referencia), para un producto o un dato. */
export function Coupon({ title, children, className = '', dark = false }: { title: ReactNode; children: ReactNode; className?: string; dark?: boolean }) {
  return (
    <div
      className={`rounded-2xl border-2 border-dashed p-4 md:p-5 ${dark ? 'border-on-panel-variant/50 bg-panel/80 text-on-panel backdrop-blur' : 'border-outline-variant bg-surface-container-lowest text-on-surface'} ${className}`}
    >
      <p className={`mb-3 border-b border-dashed pb-3 text-sm font-semibold ${dark ? 'border-on-panel-variant/40 text-on-panel-variant' : 'border-outline-variant text-on-surface-variant'}`}>
        {title}
      </p>
      {children}
    </div>
  )
}

/** Garabato decorativo de tres ondas (como el de la izquierda del título en la referencia). */
export function Squiggle({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 48 24" className={className} aria-hidden="true" focusable="false">
      <path d="M2 8q5-6 10 0t10 0t10 0t10 0M2 16q5-6 10 0t10 0t10 0t10 0" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  )
}

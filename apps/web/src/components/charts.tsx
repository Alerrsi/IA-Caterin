/**
 * Gráficos del tablero (T17), en SVG y HTML propios: sin librería, funcionan sin red y pesan poco.
 *
 * Reglas (skill dataviz + marca): barras de 24 px como máximo con la punta redondeada a 4 px y la base recta; 2 px de
 * aire entre segmentos apilados; rejilla de 1 px en `hairline`; textos siempre con tokens de texto, nunca con el color
 * de la serie; leyenda desde 2 series; tooltip al pasar el mouse, tocar o enfocar con el teclado; y cada gráfico con su
 * vista en tabla (`TableView`), para que ningún dato dependa del color ni del tooltip.
 */
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { t } from '../i18n'
import { Icon } from './Icon'

export interface Series {
  name: string
  /** Variable CSS del color, p. ej. `var(--color-chart-1)`. */
  color: string
  values: number[]
}

export interface Category {
  key: string
  /** Etiqueta corta del eje X. */
  label: string
  /** Encabezado del tooltip y nombre accesible. */
  title: string
}

/** Ancho real del contenedor, para dibujar a escala 1:1 (el texto no se encoge en el celular). */
function useWidth(fallback = 320) {
  const ref = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(fallback)
  useEffect(() => {
    const el = ref.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(([entry]) => {
      const w = Math.round(entry.contentRect.width)
      if (w > 0) setWidth(w)
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return [ref, width] as const
}

/** Paso "redondo" para el eje: 1, 2, 2,5 o 5 por potencia de 10. */
export function niceStep(max: number, ticks = 4): number {
  if (max <= 0) return 1
  const raw = max / ticks
  const pow = 10 ** Math.floor(Math.log10(raw))
  const f = raw / pow
  const nice = f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10
  return nice * pow
}

/** Rectángulo con las esquinas de arriba redondeadas y la base recta (la punta del dato). */
function topRounded(x: number, y: number, w: number, h: number, r: number): string {
  const rr = Math.min(r, w / 2, h)
  return `M${x},${y + h}V${y + rr}Q${x},${y} ${x + rr},${y}H${x + w - rr}Q${x + w},${y} ${x + w},${y + rr}V${y + h}Z`
}

export function Legend({ series }: { series: Pick<Series, 'name' | 'color'>[] }) {
  if (series.length < 2) return null
  return (
    <ul className="mb-3 flex flex-wrap gap-x-4 gap-y-1 text-sm text-on-surface-variant" aria-label="Leyenda">
      {series.map((s) => (
        <li key={s.name} className="inline-flex items-center gap-2">
          <span aria-hidden="true" className="inline-block h-3 w-3 rounded-sm" style={{ background: s.color }} />
          {s.name}
        </li>
      ))}
    </ul>
  )
}

/**
 * Columnas (apiladas si hay más de una serie), con eje Y y rejilla fina. `highlight` pone la cifra total sobre una
 * sola columna (la que cuenta la historia); el resto queda en el eje, el tooltip y la tabla.
 */
export function ColumnChart({
  label,
  categories,
  series,
  format,
  axisFormat = format,
  extra,
  highlight,
  highlightFormat = axisFormat,
  height = 220,
}: {
  label: string
  categories: Category[]
  series: Series[]
  format: (v: number) => string
  axisFormat?: (v: number) => string
  extra?: (index: number) => ReactNode
  highlight?: number
  /** Formato de la cifra destacada; por defecto el del eje (corto, para que no choque con las etiquetas). */
  highlightFormat?: (v: number) => string
  height?: number
}) {
  const [ref, width] = useWidth()
  const [active, setActive] = useState<number | null>(null)
  const totals = categories.map((_, i) => series.reduce((sum, s) => sum + (s.values[i] ?? 0), 0))
  const step = niceStep(Math.max(...totals, 0))
  const top = Math.max(step, Math.ceil(Math.max(...totals, 0) / step) * step)
  const ticks = Array.from({ length: Math.round(top / step) + 1 }, (_, i) => i * step)
  const axisW = Math.max(...ticks.map((v) => axisFormat(v).length)) * 7.5 + 10
  const padTop = 22
  const padBottom = 26
  const plotW = Math.max(width - axisW, 40)
  const plotH = height - padTop - padBottom
  const band = plotW / Math.max(categories.length, 1)
  const barW = Math.min(24, band * 0.62)
  const everyOther = band < 30
  const y = (v: number) => padTop + plotH - (v / top) * plotH

  const describe = (i: number) =>
    `${categories[i].title}: ${series.map((s) => `${s.name} ${format(s.values[i] ?? 0)}`).join(', ')}`

  const tipLeft = active === null ? 0 : Math.min(Math.max(axisW + band * active + band / 2, 90), width - 90)

  return (
    <div ref={ref} className="relative min-w-0" onPointerLeave={() => setActive(null)}>
      <Legend series={series} />
      <svg width={width} height={height} role="group" aria-label={label} className="block overflow-visible">
        {ticks.map((v) => (
          <g key={v} aria-hidden="true">
            <line x1={axisW} x2={width} y1={y(v)} y2={y(v)} stroke="var(--color-hairline)" strokeWidth={1} />
            <text
              x={axisW - 8}
              y={y(v)}
              dy="0.32em"
              textAnchor="end"
              className="num fill-on-surface-variant"
              fontSize={13}
            >
              {axisFormat(v)}
            </text>
          </g>
        ))}
        {categories.map((c, i) => {
          const cx = axisW + band * i + band / 2
          let base = 0
          const visible = series.map((s) => s.values[i] ?? 0)
          const lastIdx = visible.reduce((last, v, k) => (v > 0 ? k : last), -1)
          return (
            <g key={c.key} opacity={active === null || active === i ? 1 : 0.45} className="transition-opacity duration-150 motion-reduce:transition-none">
              {series.map((s, k) => {
                const v = visible[k]
                if (v <= 0) return null
                const y0 = y(base)
                const y1 = y(base + v)
                base += v
                const gap = k > 0 && base - v > 0 ? 2 : 0 // aire de 2 px sobre el segmento anterior
                const h = Math.max(y0 - y1 - gap, 1)
                const d =
                  k === lastIdx ? topRounded(cx - barW / 2, y1, barW, h, 4) : `M${cx - barW / 2},${y1}h${barW}v${h}h${-barW}Z`
                return <path key={s.name} d={d} fill={s.color} aria-hidden="true" />
              })}
              {highlight === i && totals[i] > 0 && (
                <text
                  x={Math.max(cx, axisW + highlightFormat(totals[i]).length * 4 + 4)}
                  y={y(totals[i]) - 6}
                  textAnchor="middle"
                  className="num fill-on-surface"
                  fontSize={13}
                  aria-hidden="true"
                >
                  {highlightFormat(totals[i])}
                </text>
              )}
              {/* Si no caben todas, una sí y una no, contando desde la última (la más reciente siempre se ve). */}
              {!everyOther || (categories.length - 1 - i) % 2 === 0 ? (
                <text
                  x={cx}
                  y={height - 6}
                  textAnchor="middle"
                  className="fill-on-surface-variant"
                  fontSize={13}
                  aria-hidden="true"
                >
                  {c.label}
                </text>
              ) : null}
              {/* Zona sensible: toda la franja, más grande que la barra. */}
              <rect
                x={axisW + band * i}
                y={padTop}
                width={band}
                height={plotH}
                fill="transparent"
                tabIndex={0}
                role="img"
                aria-label={describe(i)}
                className="cursor-pointer outline-none focus-visible:stroke-primary focus-visible:[stroke-width:2]"
                onPointerEnter={() => setActive(i)}
                onPointerDown={() => setActive(i)}
                onFocus={() => setActive(i)}
                onBlur={() => setActive(null)}
              />
            </g>
          )
        })}
      </svg>
      {active !== null && (
        <div
          aria-hidden="true"
          className="pointer-events-none absolute z-10 min-w-40 -translate-x-1/2 rounded-lg border border-hairline bg-surface-container-lowest px-3 py-2 text-sm shadow-cap"
          style={{ left: tipLeft, top: 0 }}
        >
          <p className="mb-1 font-medium text-on-surface">{categories[active].title}</p>
          {[...series].reverse().map((s) => (
            <p key={s.name} className="flex items-center gap-2">
              <span aria-hidden="true" className="inline-block h-0.5 w-3" style={{ background: s.color }} />
              <span className="num font-medium text-on-surface">{format(s.values[active] ?? 0)}</span>
              <span className="text-on-surface-variant">{s.name}</span>
            </p>
          ))}
          {extra && <div className="mt-1 text-on-surface-variant">{extra(active)}</div>}
        </div>
      )}
    </div>
  )
}

export interface BarRow {
  key: string
  label: string
  value: number
  /** Texto de la cifra en la punta (p. ej. "2.882 unid."). */
  valueLabel: string
  /** Detalle bajo la etiqueta (p. ej. "22 pedidos"). */
  detail?: string
  href?: string
}

/** Barras horizontales con el nombre arriba y la cifra a la derecha: se leen bien a 390 px y sin tooltip. */
export function BarList({ label, rows, color = 'var(--color-chart-1)' }: { label: string; rows: BarRow[]; color?: string }) {
  const max = Math.max(...rows.map((r) => r.value), 0)
  return (
    <ul aria-label={label} className="space-y-3">
      {rows.map((r) => {
        const pct = max > 0 ? Math.max((r.value / max) * 100, r.value > 0 ? 1.5 : 0) : 0
        const body = (
          <>
            <span className="flex items-baseline justify-between gap-3">
              <span className="min-w-0 text-on-surface">{r.label}</span>
              <span className="num shrink-0 text-on-surface">{r.valueLabel}</span>
            </span>
            <span aria-hidden="true" className="mt-1 block h-3 rounded-r bg-surface-container">
              <span className="block h-3 rounded-r" style={{ width: `${pct}%`, background: color }} />
            </span>
            {r.detail && <span className="mt-0.5 block text-sm text-on-surface-variant">{r.detail}</span>}
          </>
        )
        return (
          <li key={r.key}>
            {r.href ? (
              <a href={r.href} className="block rounded-lg focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/30">
                {body}
              </a>
            ) : (
              body
            )}
          </li>
        )
      })}
    </ul>
  )
}

/** Stock contra su mínimo: el relleno es el estado de aviso (con ícono y texto), la pista es su tono claro. */
export function Meter({
  label,
  detail,
  pct,
  href,
}: {
  label: string
  detail: string
  pct: number
  href?: string
}) {
  const body = (
    <>
      <span className="flex items-baseline justify-between gap-3">
        <span className="inline-flex min-w-0 items-center gap-1.5 text-on-surface">
          <Icon name="warning" className="h-4 w-4 shrink-0 text-warning" />
          {label}
        </span>
        <span className="num shrink-0 text-on-surface">{`${Math.round(pct)} %`}</span>
      </span>
      <span
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(pct)}
        aria-label={`${label}: ${detail}`}
        className="mt-1 block h-3 rounded-r bg-warning-container"
      >
        <span className="block h-3 rounded-r bg-warning" style={{ width: `${Math.max(Math.min(pct, 100), 1.5)}%` }} />
      </span>
      <span className="mt-0.5 block text-sm text-on-surface-variant">{detail}</span>
    </>
  )
  return href ? (
    <a href={href} className="block rounded-lg focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/30">
      {body}
    </a>
  ) : (
    <div>{body}</div>
  )
}

/** La tabla de cada gráfico, plegada: es la vía para leer todo sin color, sin mouse y con lector de pantalla. */
export function TableView({ caption, head, rows }: { caption: string; head: string[]; rows: (string | number)[][] }) {
  return (
    <details className="mt-3 border-t border-hairline pt-2">
      <summary className="min-h-12 cursor-pointer py-3 text-base font-medium text-primary">{t.dashboard.table}</summary>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">{caption}</caption>
          <thead>
            <tr className="text-on-surface-variant">
              {head.map((h, i) => (
                <th key={h} scope="col" className={`py-1 font-medium ${i > 0 ? 'text-right' : ''}`}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={String(r[0])} className="border-t border-hairline">
                {r.map((cell, i) =>
                  i === 0 ? (
                    <th key={i} scope="row" className="py-1.5 pr-3 font-normal text-on-surface">
                      {cell}
                    </th>
                  ) : (
                    <td key={i} className="num py-1.5 text-right text-on-surface">
                      {cell}
                    </td>
                  ),
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}

/** Cifra destacada con etiqueta y bajada. `hero` para la única cifra principal de la pantalla. */
export function StatTile({
  label,
  value,
  hint,
  hero = false,
  className = '',
}: {
  label: string
  value: string
  hint?: string
  hero?: boolean
  className?: string
}) {
  return (
    <li className={`min-w-0 p-4 md:p-5 ${hero ? 'col-span-2' : ''} ${className}`}>
      <p className="text-sm font-medium text-on-surface-variant">{label}</p>
      <p className={`num mt-1 text-on-surface ${hero ? 'text-[2rem] leading-10' : 'text-2xl'}`}>{value}</p>
      {hint && <p className="mt-0.5 text-sm text-on-surface-variant">{hint}</p>}
    </li>
  )
}

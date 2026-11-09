/** Formatos es-CL: dinero en CLP sin decimales y cantidades con coma decimal. */
import { t } from './i18n'

export function formatCLP(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  const sign = value < 0 ? '-' : ''
  const digits = Math.round(Math.abs(value))
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, '.')
  return `${sign}$${digits}`
}

/** "2500.000" -> "2.500"; "2.5" -> "2,5". Acepta los decimales en texto que entrega la API. */
export function formatQty(value: string | number): string {
  const text = typeof value === 'number' ? value.toString() : value
  const [int, frac = ''] = text.replace('-', '').split('.')
  const sign = text.startsWith('-') ? '-' : ''
  const intPart = (int || '0').replace(/^0+(?=\d)/, '').replace(/\B(?=(\d{3})+(?!\d))/g, '.')
  const fracPart = frac.replace(/0+$/, '')
  return fracPart ? `${sign}${intPart},${fracPart}` : `${sign}${intPart}`
}

/** "2026-11-14" -> "14-11-2026" (sin zona horaria: es una fecha, no un instante). */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const [y, m, d] = iso.slice(0, 10).split('-')
  return `${d}-${m}-${y}`
}

/** [2, 4] -> "martes y jueves" */
export function formatWeekdays(days: number[] | null | undefined): string {
  if (!days || days.length === 0) return ''
  const names = days.map((d) => t.weekdays[d - 1]).filter(Boolean)
  if (names.length === 1) return names[0]
  return `${names.slice(0, -1).join(', ')} y ${names[names.length - 1]}`
}

/** Convierte lo que escribe la usuaria ("2,5") al decimal que espera la API ("2.5"). */
export function parseQtyInput(raw: string): string | null {
  const cleaned = raw.trim().replace(/\s/g, '').replace(',', '.')
  if (!/^\d+(\.\d{1,3})?$/.test(cleaned)) return null
  return Number(cleaned) > 0 ? cleaned : null
}

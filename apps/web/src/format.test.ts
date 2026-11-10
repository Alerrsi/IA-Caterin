import { expect, test } from 'vitest'
import {
  formatCLP,
  formatDate,
  formatDuration,
  formatMs,
  formatPct,
  formatQty,
  formatWeekdays,
  parseMinutesSeconds,
  parseQtyInput,
} from './format'

test('formato CLP chileno', () => {
  expect(formatCLP(21000)).toBe('$21.000')
  expect(formatCLP(155552)).toBe('$155.552')
  expect(formatCLP(990)).toBe('$990')
  expect(formatCLP(1234567)).toBe('$1.234.567')
  expect(formatCLP(-5000)).toBe('-$5.000')
  expect(formatCLP(null)).toBe('—')
})

test('cantidades con coma decimal y sin ceros sobrantes', () => {
  expect(formatQty('2500.000')).toBe('2.500')
  expect(formatQty('2.500')).toBe('2,5')
  expect(formatQty('0.5')).toBe('0,5')
  expect(formatQty('80')).toBe('80')
})

test('fechas, días de despacho y entrada de cantidades', () => {
  expect(formatDate('2026-11-14')).toBe('14-11-2026')
  expect(formatWeekdays([2, 4])).toBe('martes y jueves')
  expect(formatWeekdays([1, 3, 5])).toBe('lunes, miércoles y viernes')
  expect(parseQtyInput('2,5')).toBe('2.5')
  expect(parseQtyInput('80')).toBe('80')
  expect(parseQtyInput('0')).toBeNull()
  expect(parseQtyInput('mucho')).toBeNull()
})

test('duraciones, latencias y porcentajes de las métricas', () => {
  expect(formatDuration(160.1)).toBe('2 min 40 s')
  expect(formatDuration(1500)).toBe('25 min')
  expect(formatDuration(3900)).toBe('1 h 05 min')
  expect(formatDuration(42)).toBe('42 s')
  expect(formatDuration(0.84)).toBe('0,8 s')
  expect(formatDuration(null)).toBe('—')
  expect(formatMs(850)).toBe('850 ms')
  expect(formatMs(12475)).toBe('12,5 s')
  expect(formatPct(58.3)).toBe('58,3 %')
  expect(formatPct(100)).toBe('100 %')
  expect(formatPct(null)).toBe('—')
  expect(parseMinutesSeconds('24', '30')).toBe(1470)
  expect(parseMinutesSeconds('2,5', '')).toBe(150)
  expect(parseMinutesSeconds('', '75')).toBeNull()
  expect(parseMinutesSeconds('', '')).toBeNull()
  expect(parseMinutesSeconds('-1', '0')).toBeNull()
})

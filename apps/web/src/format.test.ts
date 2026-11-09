import { expect, test } from 'vitest'
import { formatCLP, formatDate, formatQty, formatWeekdays, parseQtyInput } from './format'

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

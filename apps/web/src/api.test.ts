import { expect, test } from 'vitest'
import { ApiError } from './api'

test('el error de validación dice qué campo falló y el máximo', () => {
  const err = new ApiError(422, 'validation_error', 'Revisa los datos ingresados', undefined, [
    { field: 'customer_name', message: 'El texto es demasiado largo (máximo 120 caracteres)' },
  ])
  expect(err.userMessage).toBe(
    'Revisa los datos ingresados. Nombre del cliente: El texto es demasiado largo (máximo 120 caracteres)',
  )
})

test('un campo sin nombre conocido muestra solo el mensaje', () => {
  const err = new ApiError(422, 'validation_error', 'Revisa los datos ingresados', undefined, [
    { field: 'lines.0.recipe_id', message: 'Identificador no válido' },
  ])
  expect(err.userMessage).toBe('Revisa los datos ingresados. Identificador no válido')
})

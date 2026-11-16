import { useEffect, useState } from 'react'
import { ApiError, post, type ProductionPreview as Preview } from '../api'
import { formatStock } from '../format'
import { t } from '../i18n'
import { Icon } from './Icon'
import { useOnline } from './ui'

/**
 * Lo que va a pasar en el inventario al confirmar una producción (T18): cuánto se suma a las existencias del
 * producto y qué insumos se descuentan. Lo calcula la API (`/vision/productions/preview`), con la misma regla que la
 * confirmación. Sin señal no hay números: se explica qué se hará al volver la red.
 */
export function ProductionPreview({ recipeId, qty, consume }: { recipeId: string | null; qty: number; consume: boolean }) {
  const online = useOnline()
  const [preview, setPreview] = useState<Preview | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    if (!recipeId || !online) return
    let alive = true
    // Espera un momento: al apretar + varias veces no se pide una vista previa por cada toque.
    const timer = window.setTimeout(() => {
      post<Preview>('/vision/productions/preview', {
        recipe_id: recipeId,
        confirmed_qty: qty,
        consume_ingredients: consume,
      }).then(
        (p) => {
          if (!alive) return
          setPreview(p)
          setFailed(false)
        },
        (err: unknown) => alive && setFailed(!(err instanceof ApiError && err.status === 0)),
      )
    }, 250)
    return () => {
      alive = false
      window.clearTimeout(timer)
    }
  }, [recipeId, qty, consume, online])

  if (!recipeId || failed) return null
  if (!online) return <p className="text-sm text-on-surface-variant">{t.vision.previewOffline}</p>
  if (!preview || preview.recipe_id !== recipeId) return null
  const unit = preview.yield_unit
  const consumed = preview.consumed
  return (
    <div className="rounded-xl border-2 border-dashed border-outline-variant p-4 text-on-surface" aria-live="polite">
      <p className="text-sm font-semibold text-on-surface-variant">{t.vision.previewTitle}</p>
      <p className="mt-1">
        {t.vision.previewAdd(formatStock(preview.add_qty, unit), preview.recipe_name, formatStock(preview.product_stock_qty, unit))}
      </p>
      {!preview.consume_ingredients ? (
        <p className="mt-1 text-sm text-on-surface-variant">{t.vision.previewNoConsume}</p>
      ) : consumed.length === 0 ? (
        <p className="mt-1 text-sm text-on-surface-variant">{t.vision.previewNoLines}</p>
      ) : (
        <details className="mt-1" open={consumed.some((c) => c.went_negative)}>
          <summary className="min-h-11 cursor-pointer py-2 font-semibold text-primary">
            {t.vision.previewConsume(consumed.length)}
          </summary>
          {/* Columnas alineadas (T21): insumo a la izquierda, cuánto se usa a la derecha y lo que queda debajo. */}
          <ul className="divide-y divide-hairline text-sm">
            {consumed.map((c) => (
              <li key={c.ingredient_id} className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 py-2">
                <span className="font-semibold text-on-surface">{c.name}</span>
                <span className="num text-right text-on-surface">{formatStock(c.qty, c.base_unit)}</span>
                <span className="col-span-2 text-on-surface-variant">
                  <span className="num font-medium">{t.vision.previewLeft(formatStock(c.stock_qty, c.base_unit))}</span>
                </span>
                {c.went_negative && (
                  <span className="col-span-2 mt-1 inline-flex items-center gap-1 font-semibold text-on-warning-container">
                    <Icon name="warning" className="h-4 w-4 text-warning" />
                    {t.vision.previewNegative}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}

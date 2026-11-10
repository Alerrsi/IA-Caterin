import { useState, type FormEvent } from 'react'
import { ApiError, api, apiBlob, post, type ImportPreview, type ImportResult } from '../api'
import { useAuth } from '../auth'
import { Alert, Button, Page, Spinner, useOnline } from '../components/ui'
import { formatCLP, formatStock, type BaseUnit } from '../format'
import { t } from '../i18n'
import { navigate } from '../router'

type Kind = 'ingredients' | 'prices'

interface IngredientRow {
  row: number
  name: string
  base_unit: string
  stock_qty: string
  min_stock_qty: string | null
  category: string | null
}

interface PriceRow {
  row: number
  ingredient_name: string
  supplier_name: string
  supplier_is_new: boolean
  package_label: string
  price_clp: number
}

type Row = IngredientRow | PriceRow

function errorText(err: unknown): string {
  return err instanceof ApiError ? err.userMessage : t.genericError
}

function RowSummary({ kind, row }: { kind: Kind; row: Row }) {
  if (kind === 'ingredients') {
    const r = row as IngredientRow
    return (
      <>
        <span className="font-medium">{r.name}</span>
        <span className="text-on-surface-variant">
          {' '}
          · {formatStock(r.stock_qty, r.base_unit as BaseUnit)}
          {r.category ? ` · ${r.category}` : ''}
        </span>
      </>
    )
  }
  const r = row as PriceRow
  return (
    <>
      <span className="font-medium">{r.ingredient_name}</span>
      <span className="text-on-surface-variant">
        {' '}
        · {r.supplier_name}
        {r.supplier_is_new && ` (${t.imports.newSupplier})`} · {r.package_label} · {formatCLP(r.price_clp)}
      </span>
    </>
  )
}

export default function Imports() {
  const { user } = useAuth()
  const online = useOnline()
  const [kind, setKind] = useState<Kind>('ingredients')
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<ImportPreview<Row> | null>(null)
  const [result, setResult] = useState<ImportResult | null>(null)
  const [undone, setUndone] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  function reset(next: Partial<{ kind: Kind; file: File | null }> = {}) {
    if (next.kind) setKind(next.kind)
    if ('file' in next) setFile(next.file ?? null)
    setPreview(null)
    setResult(null)
    setUndone(false)
    setError(null)
  }

  async function run(fn: () => Promise<void>) {
    setBusy(true)
    setError(null)
    try {
      await fn()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  const downloadTemplate = () =>
    run(async () => {
      const blob = await apiBlob(`/imports/templates/${kind}.csv`)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `plantilla-${kind === 'ingredients' ? 'insumos' : 'precios'}.csv`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    })

  const review = (e: FormEvent) => {
    e.preventDefault()
    if (!file) return
    void run(async () => {
      const form = new FormData()
      form.append('file', file, file.name)
      setPreview(await api<ImportPreview<Row>>(`/imports/${kind}/preview`, { method: 'POST', body: form }))
      setResult(null)
      setUndone(false)
    })
  }

  const confirm = () =>
    run(async () => {
      if (!preview) return
      const body = kind === 'prices' ? { rows: preview.valid, source: preview.source } : { rows: preview.valid }
      setResult(await post<ImportResult>(`/imports/${kind}/confirm`, body))
    })

  const undo = () =>
    run(async () => {
      if (!result) return
      await api<void>(`/imports/${result.import_batch_id}`, { method: 'DELETE' })
      setUndone(true)
    })

  if (user?.role !== 'owner') {
    return (
      <Page title={t.imports.title} onBack={() => navigate('/')} size="narrow">
        <Alert kind="info">{t.imports.ownerOnly}</Alert>
      </Page>
    )
  }

  return (
    <Page title={t.imports.title} onBack={() => navigate('/')} size="narrow">
      {!online && (
        <div className="mb-4">
          <Alert kind="warning">{t.sync.needsNetwork}</Alert>
        </div>
      )}
      <form onSubmit={review} className="space-y-4 rounded-xl bg-surface-container-lowest p-4 border border-outline-variant">
        <fieldset>
          <legend className="mb-2 font-medium text-on-surface">{t.imports.what}</legend>
          <div className="flex flex-wrap gap-2">
            {(['ingredients', 'prices'] as Kind[]).map((k) => (
              <label
                key={k}
                className={`flex min-h-12 cursor-pointer items-center gap-2 rounded-xl border-2 px-4 text-lg ${
                  kind === k ? 'border-primary bg-surface-container font-medium text-primary' : 'border-outline'
                }`}
              >
                <input
                  type="radio"
                  name="kind"
                  value={k}
                  checked={kind === k}
                  onChange={() => reset({ kind: k })}
                  className="h-5 w-5 accent-primary"
                />
                {t.imports.kinds[k]}
              </label>
            ))}
          </div>
        </fieldset>
        <Button variant="ghost" onClick={() => void downloadTemplate()} disabled={busy || !online}>
          {t.imports.template}
        </Button>
        <div>
          <p className="mb-1 font-medium text-on-surface">{t.imports.file}</p>
          {/* Botón propio: el selector nativo muestra "Choose File" en inglés */}
          <label className="flex min-h-12 w-full cursor-pointer items-center rounded-full border border-outline bg-transparent px-6 py-3 text-base font-medium text-primary hover:bg-primary/8 focus-within:ring-4 focus-within:ring-primary/40">
            <span className="truncate">{file ? t.imports.chosen(file.name) : t.imports.chooseFile}</span>
            <input
              className="sr-only"
              type="file"
              aria-label={t.imports.file}
              accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              onChange={(e) => reset({ file: e.target.files?.[0] ?? null })}
            />
          </label>
        </div>
        <Button type="submit" className="w-full" disabled={busy || !online || !file}>
          {busy && !preview ? t.imports.reading : t.imports.preview}
        </Button>
      </form>

      {error && (
        <div className="mt-4">
          <Alert>{error}</Alert>
        </div>
      )}
      {busy && preview && (
        <div className="mt-4">
          <Spinner label={t.imports.loading} />
        </div>
      )}

      {preview && (
        <section className="mt-6 space-y-4" aria-live="polite">
          <p className="text-lg font-medium text-on-surface">{t.imports.summary(preview.valid.length, preview.total_rows)}</p>
          {preview.valid.length > 0 && (
            <ul className="divide-y divide-outline-variant rounded-xl bg-surface-container-lowest px-4 border border-outline-variant">
              {preview.valid.map((r) => (
                <li key={r.row} className="py-2">
                  <span className="text-sm text-on-surface-variant">{t.imports.row(r.row)} · </span>
                  <RowSummary kind={kind} row={r} />
                </li>
              ))}
            </ul>
          )}
          {preview.errors.length > 0 && (
            <div className="rounded-xl border-l-4 border-warning bg-warning-container p-4 text-on-warning-container">
              <h2 className="font-medium">{t.imports.errors}</h2>
              <ul className="mt-2 space-y-1">
                {preview.errors.map((e, i) => (
                  <li key={`${e.row}-${e.field}-${i}`}>
                    {t.imports.row(e.row)} · {e.field}: {e.message}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {preview.valid.length === 0 ? (
            <Alert kind="warning">{t.imports.nothingValid}</Alert>
          ) : (
            !result && (
              <Button className="w-full" onClick={() => void confirm()} disabled={busy || !online}>
                {t.imports.confirm(preview.valid.length)}
              </Button>
            )
          )}
        </section>
      )}

      {result && (
        <section className="mt-6 space-y-3" aria-live="polite">
          {undone ? (
            <Alert kind="info">{t.imports.undone}</Alert>
          ) : (
            <>
              <Alert kind="info">
                {t.imports.done(result.created)}
                {result.suppliers_created > 0 && ` ${t.imports.suppliersCreated(result.suppliers_created)}`}
              </Alert>
              <Button variant="secondary" className="w-full" onClick={() => void undo()} disabled={busy || !online}>
                {t.imports.undo}
              </Button>
            </>
          )}
        </section>
      )}
    </Page>
  )
}

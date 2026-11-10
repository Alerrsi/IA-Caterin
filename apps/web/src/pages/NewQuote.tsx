import { useEffect, useRef, useState } from 'react'
import {
  api,
  ApiError,
  post,
  sendQuoteTiming,
  type Extraction,
  type OrderOut,
  type OrderUnit,
  type PortalRequest,
  type QuoteOut,
  type Suggestion,
} from '../api'
import { MarginFix, isMarginRequired } from '../components/MarginFix'
import { Alert, Button, Field, inputClass, Page, Spinner } from '../components/ui'
import { formatQty, parseQtyInput } from '../format'
import { t } from '../i18n'
import { navigate } from '../router'

const UNITS: OrderUnit[] = ['unit', 'dozen', 'kg', 'g', 'l', 'ml']

interface Line {
  key: number
  requested_name: string
  recipe_id: string
  qty: string
  unit: OrderUnit
  suggestions: Suggestion[]
  warning: string | null
}

let nextKey = 1
const emptyLine = (): Line => ({
  key: nextKey++,
  requested_name: '',
  recipe_id: '',
  qty: '',
  unit: 'unit',
  suggestions: [],
  warning: null,
})

/**
 * Cotizar un pedido. La dueña y el cliente del portal (ADR-007) usan el mismo flujo: pegar o escribir el pedido,
 * revisar la tabla y calcular. El cliente no escribe su nombre (es su cuenta), puede dejar un comentario y su
 * cotización queda guardada para enviarla después.
 */
export default function NewQuote({ portal = false }: { portal?: boolean }) {
  const startedAt = useRef(new Date().toISOString())
  const [step, setStep] = useState<'paste' | 'review'>('paste')
  const [text, setText] = useState('')
  const [reading, setReading] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [recipes, setRecipes] = useState<{ id: string; name: string }[]>([])
  const [notes, setNotes] = useState('')
  const [customer, setCustomer] = useState('')
  const [eventDate, setEventDate] = useState('')
  const [guests, setGuests] = useState('')
  const [lines, setLines] = useState<Line[]>([emptyLine()])
  const [source, setSource] = useState<'text' | 'form'>('form')
  const [extraction, setExtraction] = useState<Record<string, unknown> | null>(null)
  const [saving, setSaving] = useState(false)
  // Si el pedido ya se guardó y lo que falló fue la cotización (p. ej. sin margen), se reintenta sin duplicarlo.
  const [savedOrderId, setSavedOrderId] = useState<string | null>(null)
  const [needsMargin, setNeedsMargin] = useState(false)

  useEffect(() => {
    api<{ id: string; name: string }[]>(portal ? '/portal/products' : '/recipes')
      .then(setRecipes)
      .catch((err) => setError(err instanceof ApiError ? err.userMessage : t.genericError))
  }, [portal])

  async function read() {
    setReading(true)
    setError(null)
    setNotice(null)
    try {
      const out = await post<Extraction>(portal ? '/portal/extract' : '/orders/extract', { text })
      setLines(
        out.lines.length
          ? out.lines.map((l) => ({
              key: nextKey++,
              requested_name: l.requested_name,
              recipe_id: l.recipe_id ?? '',
              qty: formatQty(l.qty),
              unit: l.unit === 'portion' ? 'unit' : l.unit,
              suggestions: l.suggestions,
              warning: l.warning,
            }))
          : [emptyLine()],
      )
      setGuests(out.guests ? String(out.guests) : '')
      setEventDate(out.event_date ?? '')
      setSource('text')
      setExtraction(out.extraction)
      setStep('review')
    } catch (err) {
      if (err instanceof ApiError && ['extraction_failed', 'llm_unavailable', 'too_many_reads'].includes(err.code)) {
        setNotice(err.code === 'too_many_reads' ? t.portal.tooMany : err.userMessage)
        setLines([emptyLine()])
        setSource('form')
        setStep('review')
      } else {
        setError(err instanceof ApiError ? err.userMessage : t.genericError)
      }
    } finally {
      setReading(false)
    }
  }

  function manual() {
    setSource('form')
    setNotice(null)
    setLines([emptyLine()])
    setStep('review')
  }

  function update(key: number, change: Partial<Line>) {
    setLines((prev) => prev.map((l) => (l.key === key ? { ...l, ...change } : l)))
  }

  async function confirm() {
    setError(null)
    if (!portal && customer.trim().length < 2) return setError(t.quote.missingCustomer)
    if (lines.some((l) => !l.recipe_id)) return setError(portal ? t.portal.missingProduct : t.quote.missingRecipe)
    const parsed = lines.map((l) => parseQtyInput(l.qty))
    if (parsed.some((q) => q === null)) return setError(t.quote.badQty)
    setSaving(true)
    if (portal) return saveRequest(parsed as string[])
    let orderId = savedOrderId
    try {
      if (!orderId) {
        const order = await post<OrderOut>('/orders', {
        customer_name: customer.trim(),
        event_date: eventDate || null,
        guests: guests ? Number(guests) : null,
        source,
        raw_text: source === 'text' ? text : null,
        extraction: source === 'text' ? extraction : null,
        lines: lines.map((l, i) => ({
          recipe_id: l.recipe_id,
          requested_name: l.requested_name || null,
          qty: parsed[i],
          unit: l.unit,
        })),
        })
        orderId = order.id
        setSavedOrderId(order.id)
      }
      const quote = await post<QuoteOut>(`/orders/${orderId}/quotes`, {})
      // Métrica T09: desde que se abrió esta pantalla hasta tener la cotización calculada.
      sendQuoteTiming({ started_at: startedAt.current, ended_at: new Date().toISOString(), quote_id: quote.id, source })
      navigate(`/cotizaciones/${quote.id}`)
    } catch (err) {
      if (isMarginRequired(err)) {
        setNeedsMargin(true)
        return
      }
      setSavedOrderId(null) // otro error: si la usuaria corrige el pedido, se guarda de nuevo
      if (err instanceof ApiError && err.status === 403) setError(t.quote.ownerOnly)
      else setError(err instanceof ApiError ? err.userMessage : t.genericError)
    } finally {
      setSaving(false)
    }
  }

  async function saveRequest(parsed: string[]) {
    try {
      const req = await post<PortalRequest>('/portal/requests', {
        event_date: eventDate || null,
        guests: guests ? Number(guests) : null,
        notes: notes.trim() || null,
        source,
        raw_text: source === 'text' ? text : null,
        extraction: source === 'text' ? extraction : null,
        lines: lines.map((l, i) => ({ recipe_id: l.recipe_id, requested_name: l.requested_name || null, qty: parsed[i], unit: l.unit })),
      })
      navigate(`/solicitudes/${req.id}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.userMessage : t.genericError)
    } finally {
      setSaving(false)
    }
  }

  if (step === 'paste') {
    return (
      <Page title={t.quote.title} onBack={() => navigate('/')} size="narrow">
        <p className="mb-3 font-medium text-on-surface-variant">{t.quote.step1}</p>
        <Field label={portal ? t.portal.pasteLabel : t.quote.pasteLabel}>
          <textarea
            className={`${inputClass} min-h-40`}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={portal ? t.portal.pastePlaceholder : t.quote.pastePlaceholder}
            maxLength={2000}
            disabled={reading}
          />
        </Field>
        <div className="mt-4 space-y-3">
          {reading ? (
            <Spinner label={t.quote.reading} />
          ) : (
            <Button className="w-full" onClick={read} disabled={text.trim().length < 3}>
              {t.quote.read}
            </Button>
          )}
          <Button variant="secondary" className="w-full" onClick={manual} disabled={reading}>
            {t.quote.manual}
          </Button>
          {error && <Alert>{error}</Alert>}
        </div>
      </Page>
    )
  }

  return (
    <Page title={t.quote.title} onBack={() => setStep('paste')}>
      <p className="font-medium text-on-surface-variant">{t.quote.step2}</p>
      <p className="mb-4 text-on-surface-variant">{t.quote.reviewHint}</p>
      {notice && (
        <div className="mb-4">
          <Alert kind="warning">{notice}</Alert>
        </div>
      )}
      <div className="space-y-4">
        {!portal && (
          <Field label={t.quote.customer}>
            <input className={inputClass} value={customer} onChange={(e) => setCustomer(e.target.value)} autoComplete="off" />
          </Field>
        )}
        <div className="grid grid-cols-2 gap-3">
          <Field label={t.quote.eventDate}>
            <input type="date" className={inputClass} value={eventDate} onChange={(e) => setEventDate(e.target.value)} />
          </Field>
          <Field label={t.quote.guests}>
            <input
              type="number"
              inputMode="numeric"
              min={1}
              className={inputClass}
              value={guests}
              onChange={(e) => setGuests(e.target.value)}
            />
          </Field>
        </div>
      </div>

      <h2 className="mb-2 mt-6 text-xl font-medium text-on-surface">{t.quote.products}</h2>
      <ul className="grid items-start gap-4 lg:grid-cols-2">
        {lines.map((line, idx) => (
          <li key={line.key} className="rounded-xl bg-surface-container-lowest p-4 border border-outline-variant" data-testid="order-line">
            {line.requested_name && (
              <p className="mb-2 text-sm text-on-surface-variant">
                {portal ? t.portal.asked(line.requested_name) : t.quote.asked(line.requested_name)}
              </p>
            )}
            <Field label={`${portal ? t.portal.product : t.quote.recipe} ${idx + 1}`}>
              <select
                className={inputClass}
                value={line.recipe_id}
                onChange={(e) => update(line.key, { recipe_id: e.target.value, warning: null })}
              >
                <option value="">{portal ? t.portal.chooseProduct : t.quote.chooseRecipe}</option>
                {recipes.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </select>
            </Field>
            {!line.recipe_id && (
              <div className="mt-2">
                <Alert kind="warning">
                  <p>
                    {line.suggestions.length
                      ? portal
                        ? t.portal.suggestions
                        : t.quote.suggestions
                      : (line.warning ?? (portal ? t.portal.noProduct : t.quote.noRecipe))}
                  </p>
                  {line.suggestions.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {line.suggestions.map((s) => (
                        <Button
                          key={s.recipe_id}
                          variant="secondary"
                          className="!min-h-10 !py-1 !text-base"
                          onClick={() => update(line.key, { recipe_id: s.recipe_id, warning: null })}
                        >
                          {s.recipe_name}
                        </Button>
                      ))}
                    </div>
                  )}
                </Alert>
              </div>
            )}
            <div className="mt-3 grid grid-cols-2 gap-3">
              <Field label={t.quote.qty}>
                <input
                  className={inputClass}
                  inputMode="decimal"
                  value={line.qty}
                  onChange={(e) => update(line.key, { qty: e.target.value })}
                />
              </Field>
              <Field label={t.quote.unit}>
                <select
                  className={inputClass}
                  value={line.unit}
                  onChange={(e) => update(line.key, { unit: e.target.value as OrderUnit })}
                >
                  {UNITS.map((u) => (
                    <option key={u} value={u}>
                      {t.units[u]}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
            {lines.length > 1 && (
              <Button
                variant="ghost"
                className="mt-2"
                onClick={() => setLines((prev) => prev.filter((l) => l.key !== line.key))}
              >
                {t.quote.removeLine}
              </Button>
            )}
          </li>
        ))}
      </ul>
      <Button variant="secondary" className="mt-4 w-full" onClick={() => setLines((p) => [...p, emptyLine()])}>
        {t.quote.addLine}
      </Button>
      {portal && (
        <div className="mt-4">
          <Field label={t.portal.notes}>
            <textarea
              className={`${inputClass} min-h-24`}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              maxLength={2000}
            />
          </Field>
        </div>
      )}
      {error && (
        <div className="mt-4">
          <Alert>{error}</Alert>
        </div>
      )}
      {needsMargin && (
        <div className="mt-4">
          <MarginFix
            onSaved={async () => {
              setNeedsMargin(false)
              await confirm()
            }}
          />
        </div>
      )}
      <Button className="mt-4 w-full" onClick={confirm} disabled={saving}>
        {saving ? t.quote.calculating : portal ? t.portal.confirm : t.quote.confirm}
      </Button>
    </Page>
  )
}

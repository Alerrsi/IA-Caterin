import { useEffect, useRef, useState } from 'react'
import {
  api,
  ApiError,
  post,
  sendQuoteTiming,
  type Extraction,
  type OrderOut,
  type OrderUnit,
  type QuoteOut,
  type RecipeSummary,
  type Suggestion,
} from '../api'
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

export default function NewQuote() {
  const startedAt = useRef(new Date().toISOString())
  const [step, setStep] = useState<'paste' | 'review'>('paste')
  const [text, setText] = useState('')
  const [reading, setReading] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [recipes, setRecipes] = useState<RecipeSummary[]>([])
  const [customer, setCustomer] = useState('')
  const [eventDate, setEventDate] = useState('')
  const [guests, setGuests] = useState('')
  const [lines, setLines] = useState<Line[]>([emptyLine()])
  const [source, setSource] = useState<'text' | 'form'>('form')
  const [extraction, setExtraction] = useState<Record<string, unknown> | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api<RecipeSummary[]>('/recipes')
      .then(setRecipes)
      .catch((err) => setError(err instanceof ApiError ? err.userMessage : t.genericError))
  }, [])

  async function read() {
    setReading(true)
    setError(null)
    setNotice(null)
    try {
      const out = await post<Extraction>('/orders/extract', { text })
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
      if (err instanceof ApiError && ['extraction_failed', 'llm_unavailable'].includes(err.code)) {
        setNotice(err.userMessage)
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
    if (customer.trim().length < 2) return setError(t.quote.missingCustomer)
    if (lines.some((l) => !l.recipe_id)) return setError(t.quote.missingRecipe)
    const parsed = lines.map((l) => parseQtyInput(l.qty))
    if (parsed.some((q) => q === null)) return setError(t.quote.badQty)
    setSaving(true)
    try {
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
      const quote = await post<QuoteOut>(`/orders/${order.id}/quotes`, {})
      // Métrica T09: desde que se abrió esta pantalla hasta tener la cotización calculada.
      sendQuoteTiming({ started_at: startedAt.current, ended_at: new Date().toISOString(), quote_id: quote.id, source })
      navigate(`/cotizaciones/${quote.id}`)
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) setError(t.quote.ownerOnly)
      else setError(err instanceof ApiError ? err.userMessage : t.genericError)
    } finally {
      setSaving(false)
    }
  }

  if (step === 'paste') {
    return (
      <Page title={t.quote.title} onBack={() => navigate('/')}>
        <p className="mb-3 font-semibold text-stone-700">{t.quote.step1}</p>
        <Field label={t.quote.pasteLabel}>
          <textarea
            className={`${inputClass} min-h-40`}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={t.quote.pastePlaceholder}
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
      <p className="font-semibold text-stone-700">{t.quote.step2}</p>
      <p className="mb-4 text-stone-700">{t.quote.reviewHint}</p>
      {notice && (
        <div className="mb-4">
          <Alert kind="warning">{notice}</Alert>
        </div>
      )}
      <div className="space-y-4">
        <Field label={t.quote.customer}>
          <input className={inputClass} value={customer} onChange={(e) => setCustomer(e.target.value)} autoComplete="off" />
        </Field>
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

      <h2 className="mb-2 mt-6 text-xl font-bold text-stone-900">{t.quote.products}</h2>
      <ul className="space-y-4">
        {lines.map((line, idx) => (
          <li key={line.key} className="rounded-2xl bg-white p-4 shadow-sm" data-testid="order-line">
            {line.requested_name && <p className="mb-2 text-sm text-stone-600">{t.quote.asked(line.requested_name)}</p>}
            <Field label={`${t.quote.recipe} ${idx + 1}`}>
              <select
                className={inputClass}
                value={line.recipe_id}
                onChange={(e) => update(line.key, { recipe_id: e.target.value, warning: null })}
              >
                <option value="">{t.quote.chooseRecipe}</option>
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
                  <p>{line.suggestions.length ? t.quote.suggestions : (line.warning ?? t.quote.noRecipe)}</p>
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
      {error && (
        <div className="mt-4">
          <Alert>{error}</Alert>
        </div>
      )}
      <Button className="mt-4 w-full" onClick={confirm} disabled={saving}>
        {saving ? t.quote.calculating : t.quote.confirm}
      </Button>
    </Page>
  )
}

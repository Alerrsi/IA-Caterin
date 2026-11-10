import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { api, apiBlob, ApiError, post, type MetricsSummary, type MetricStat } from '../api'
import { useAuth } from '../auth'
import { Alert, Button, Field, inputClass, Page, Spinner } from '../components/ui'
import { formatDate, formatDuration, formatMs, formatPct, formatQty, parseMinutesSeconds } from '../format'
import { t } from '../i18n'
import { navigate } from '../router'

type PeriodKey = '7' | '30' | '90' | 'all'

/** Fecha local "AAAA-MM-DD" de hace `days` días (para el filtro del periodo). */
function daysAgo(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() - days)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function query(period: PeriodKey): string {
  return period === 'all' ? '' : `?from=${daysAgo(Number(period) - 1)}`
}

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-xl bg-surface-container-lowest p-5 border border-outline-variant" aria-label={title}>
      <h2 className="mb-2 text-xl font-medium">{title}</h2>
      {children}
    </section>
  )
}

/** Aviso de n bajo. Con n = 0 no se muestra: ahí ya dice "Sin datos". */
function LowN({ n, show, min }: { n: number; show: boolean; min: number }) {
  if (!show || n === 0) return null
  return <p className="mt-1 text-sm font-medium text-on-warning-container">{t.metrics.lowN(min)}</p>
}

function StatRow({ label, stat, min, format }: { label: string; stat: MetricStat; min: number; format: (v: number | null) => string }) {
  return (
    <div className="py-2">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-on-surface">{label}</span>
        {stat.value === null ? (
          <span className="shrink-0 text-lg text-on-surface-variant">{t.metrics.noData}</span>
        ) : (
          <span className="shrink-0 text-2xl font-medium text-on-surface">{format(stat.value)}</span>
        )}
      </div>
      <p className="text-sm text-on-surface-variant">{t.metrics.n(stat.n)}</p>
      <LowN n={stat.n} show={stat.low_n} min={min} />
    </div>
  )
}

function measured(range: { first_measured_on: string | null; last_measured_on: string | null }) {
  if (!range.first_measured_on || !range.last_measured_on) return null
  return (
    <p className="text-sm text-on-surface-variant">
      {t.metrics.measuredBetween(formatDate(range.first_measured_on), formatDate(range.last_measured_on))}
    </p>
  )
}

function BaselineForm({ onSaved }: { onSaved: () => void }) {
  const [task, setTask] = useState<'quote' | 'data_lookup'>('quote')
  const [minutes, setMinutes] = useState('')
  const [seconds, setSeconds] = useState('')
  const [reference, setReference] = useState('')
  const [repetition, setRepetition] = useState('1')
  const [measuredOn, setMeasuredOn] = useState(daysAgo(0))
  const [tool, setTool] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSaved(false)
    const total = parseMinutesSeconds(minutes, seconds)
    if (total === null) return setError(t.metrics.badTime)
    if (reference.trim().length < 2) return setError(t.metrics.missingReference)
    setSaving(true)
    try {
      await post('/metrics/manual-baseline', {
        task,
        seconds: total,
        reference: reference.trim(),
        repetition: Number(repetition) || 1,
        measured_on: measuredOn,
        tool: tool.trim() || null,
      })
      setSaved(true)
      setMinutes('')
      setSeconds('')
      setRepetition(String((Number(repetition) || 1) + 1))
      onSaved()
    } catch (err) {
      setError(err instanceof ApiError ? err.userMessage : t.genericError)
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3" noValidate>
      <p className="text-on-surface-variant">{t.metrics.baselineHint}</p>
      <Field label={t.metrics.task}>
        <select className={inputClass} value={task} onChange={(e) => setTask(e.target.value as typeof task)}>
          <option value="quote">{t.metrics.tasks.quote}</option>
          <option value="data_lookup">{t.metrics.tasks.data_lookup}</option>
        </select>
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label={t.metrics.minutes}>
          <input className={inputClass} inputMode="decimal" value={minutes} onChange={(e) => setMinutes(e.target.value)} />
        </Field>
        <Field label={t.metrics.seconds}>
          <input className={inputClass} inputMode="numeric" value={seconds} onChange={(e) => setSeconds(e.target.value)} />
        </Field>
      </div>
      <Field label={t.metrics.reference}>
        <input
          className={inputClass}
          value={reference}
          placeholder={t.metrics.referencePlaceholder}
          onChange={(e) => setReference(e.target.value)}
        />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label={t.metrics.repetition}>
          <input className={inputClass} type="number" min={1} value={repetition} onChange={(e) => setRepetition(e.target.value)} />
        </Field>
        <Field label={t.metrics.measuredOn}>
          <input className={inputClass} type="date" value={measuredOn} onChange={(e) => setMeasuredOn(e.target.value)} />
        </Field>
      </div>
      <Field label={t.metrics.tool}>
        <input className={inputClass} value={tool} placeholder={t.metrics.toolPlaceholder} onChange={(e) => setTool(e.target.value)} />
      </Field>
      {error && <Alert>{error}</Alert>}
      {saved && <Alert kind="info">{t.metrics.saved}</Alert>}
      <Button type="submit" className="w-full" disabled={saving}>
        {saving ? t.metrics.saving : t.metrics.save}
      </Button>
    </form>
  )
}

export default function Metrics() {
  const { user } = useAuth()
  const [period, setPeriod] = useState<PeriodKey>('30')
  const [summary, setSummary] = useState<MetricsSummary | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [downloading, setDownloading] = useState(false)

  const load = useCallback(() => {
    api<MetricsSummary>(`/metrics/summary${query(period)}`)
      .then((s) => {
        setSummary(s)
        setError(null)
      })
      .catch((err) => setError(err instanceof ApiError ? err.userMessage : t.genericError))
  }, [period])

  useEffect(() => {
    if (user?.role === 'owner') load()
  }, [load, user])

  async function download() {
    setDownloading(true)
    setError(null)
    try {
      const blob = await apiBlob(`/metrics/summary.csv${query(period)}`)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `metricas-caterin-${summary?.period.date_to ?? daysAgo(0)}.csv`
      document.body.appendChild(a)
      a.click()
      a.remove()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (err) {
      setError(err instanceof ApiError ? err.userMessage : t.genericError)
    } finally {
      setDownloading(false)
    }
  }

  if (user?.role !== 'owner') {
    return (
      <Page title={t.metrics.title} onBack={() => navigate('/')}>
        <Alert>{t.metrics.ownerOnly}</Alert>
      </Page>
    )
  }

  const min = summary?.low_n_threshold ?? 5
  return (
    <Page title={t.metrics.title} onBack={() => navigate('/')}>
      <p className="mb-3 text-on-surface-variant">{t.metrics.intro}</p>
      <Field label={t.metrics.period}>
        <select className={inputClass} value={period} onChange={(e) => setPeriod(e.target.value as PeriodKey)}>
          {(['7', '30', '90', 'all'] as const).map((k) => (
            <option key={k} value={k}>
              {t.metrics.periods[k]}
            </option>
          ))}
        </select>
      </Field>

      {error && (
        <div className="mt-4">
          <Alert>{error}</Alert>
        </div>
      )}
      {!summary ? (
        !error && (
          <div className="mt-4">
            <Spinner label={t.loading} />
          </div>
        )
      ) : (
        <div className="mt-4 space-y-4">
          <p className="font-medium text-on-surface" data-testid="metrics-period">
            {t.metrics.periodLabel(summary.period.date_from && formatDate(summary.period.date_from), formatDate(summary.period.date_to))}
          </p>

          {summary.warnings.length > 0 && (
            <Alert kind="warning">
              <p className="font-medium">{t.metrics.warnings}</p>
              <ul className="ml-5 list-disc">
                {summary.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            </Alert>
          )}

          <Card title={t.metrics.satisfaction}>
            <p className="text-3xl font-medium text-on-surface">
              {summary.satisfaction.mean_stars === null
                ? t.metrics.noData
                : t.metrics.stars(formatQty(summary.satisfaction.mean_stars.toFixed(2)))}
            </p>
            <p className="text-sm text-on-surface-variant">{t.metrics.n(summary.satisfaction.n)}</p>
            <LowN n={summary.satisfaction.n} show={summary.satisfaction.low_n} min={min} />
          </Card>

          <Card title={t.metrics.quoteTime}>
            <StatRow label={t.metrics.withCaterin} stat={summary.quote_time.caterin_median} min={min} format={formatDuration} />
            <StatRow label={t.metrics.manual} stat={summary.quote_time.manual_median} min={min} format={formatDuration} />
            {measured(summary.quote_time.manual_range)}
          </Card>

          <Card title={t.metrics.lookup}>
            <StatRow label={t.metrics.withAssistant} stat={summary.data_lookup.assistant_median} min={min} format={formatDuration} />
            <StatRow label={t.metrics.manual} stat={summary.data_lookup.manual_median} min={min} format={formatDuration} />
            {measured(summary.data_lookup.manual_range)}
          </Card>

          <Card title={t.metrics.assistant}>
            <table className="w-full text-left">
              <thead>
                <tr className="text-on-surface-variant">
                  <th className="py-1 font-medium" scope="col"></th>
                  <th className="py-1 font-medium" scope="col">n</th>
                  <th className="py-1 text-right font-medium" scope="col">{t.metrics.p50}</th>
                  <th className="py-1 text-right font-medium" scope="col">{t.metrics.p95}</th>
                </tr>
              </thead>
              <tbody>
                {summary.assistant.levels.map((lv) => (
                  <tr key={lv.level} className="border-t border-outline-variant">
                    <th scope="row" className="py-2 font-medium">
                      {t.metrics.level(lv.level)}
                    </th>
                    <td className={lv.low_n ? 'text-on-warning-container' : ''}>{lv.n}</td>
                    <td className="text-right">{formatMs(lv.p50_ms)}</td>
                    <td className="text-right">{formatMs(lv.p95_ms)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {[
              { label: t.metrics.withoutLlm, s: summary.assistant.without_llm },
              { label: t.metrics.degraded, s: summary.assistant.degraded },
            ].map(({ label, s }) => (
              <div key={label} className="mt-3">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="text-on-surface">{label}</span>
                  <span className="text-2xl font-medium text-on-surface">{formatPct(s.pct)}</span>
                </div>
                <p className="text-sm text-on-surface-variant">
                  {t.metrics.ofTotal(s.n, s.total)} · {t.metrics.n(s.total)}
                </p>
                <LowN n={s.total} show={s.low_n} min={min} />
              </div>
            ))}
          </Card>

          <Button variant="secondary" className="w-full" onClick={download} disabled={downloading}>
            {downloading ? t.metrics.downloading : t.metrics.download}
          </Button>

          <details className="rounded-xl bg-surface-container-lowest p-4 border border-outline-variant">
            <summary className="min-h-12 cursor-pointer py-2 text-xl font-medium">{t.metrics.baselineTitle}</summary>
            <BaselineForm onSaved={load} />
          </details>
        </div>
      )}
    </Page>
  )
}

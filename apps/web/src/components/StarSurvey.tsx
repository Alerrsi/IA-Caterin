import { useState } from 'react'
import { t } from '../i18n'
import { enqueue } from '../offline/queue'

/** Encuesta de 1 a 5 estrellas (métrica T09). Un toque y listo; sin señal queda en la cola y se envía después. */
export function StarSurvey({ context }: { context: 'general' | 'quote' | 'assistant' | 'vision' }) {
  const [sent, setSent] = useState<number | null>(null)
  if (sent !== null) {
    return (
      <p role="status" className="rounded-xl bg-surface-container-lowest p-4 text-center font-medium text-on-surface border border-outline-variant">
        {t.survey.thanks}
      </p>
    )
  }
  return (
    <fieldset className="rounded-xl bg-surface-container-lowest p-4 border border-outline-variant">
      <legend className="sr-only">{t.survey.questions[context]}</legend>
      <p aria-hidden="true" className="mb-2 font-medium text-on-surface">
        {t.survey.questions[context]}
      </p>
      <div className="flex justify-between gap-1">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            aria-label={t.survey.star(n)}
            onClick={() => {
              setSent(n)
              void enqueue({ path: '/metrics/survey', body: { stars: n, context }, label: t.survey.star(n) })
            }}
            className="min-h-12 min-w-12 rounded-xl text-3xl text-on-warning-container hover:bg-warning-container focus-visible:ring-4 focus-visible:ring-primary/40"
          >
            ★
          </button>
        ))}
      </div>
    </fieldset>
  )
}

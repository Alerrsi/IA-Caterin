import { useState } from 'react'
import { t } from '../i18n'
import { enqueue } from '../offline/queue'

/** Encuesta de 1 a 5 estrellas (métrica T09). Un toque y listo; sin señal queda en la cola y se envía después. */
export function StarSurvey({ context }: { context: 'general' | 'quote' | 'assistant' | 'vision' }) {
  const [sent, setSent] = useState<number | null>(null)
  if (sent !== null) {
    return (
      <p role="status" className="rounded-2xl bg-white p-4 text-center font-semibold text-stone-800 shadow-sm">
        {t.survey.thanks}
      </p>
    )
  }
  return (
    <fieldset className="rounded-2xl bg-white p-4 shadow-sm">
      <legend className="sr-only">{t.survey.questions[context]}</legend>
      <p aria-hidden="true" className="mb-2 font-semibold text-stone-800">
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
            className="min-h-12 min-w-12 rounded-xl text-3xl text-amber-600 hover:bg-amber-50 focus-visible:ring-4 focus-visible:ring-orange-300"
          >
            ★
          </button>
        ))}
      </div>
    </fieldset>
  )
}

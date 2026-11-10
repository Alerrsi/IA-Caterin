import { useState } from 'react'
import { post } from '../api'
import { t } from '../i18n'

/** Encuesta de 1 a 5 estrellas (métrica T09). Un toque y listo; si falla la red no molesta a la usuaria. */
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
      <legend className="sr-only">{t.survey.question}</legend>
      <p aria-hidden="true" className="mb-2 font-semibold text-stone-800">
        {t.survey.question}
      </p>
      <div className="flex justify-between gap-1">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            aria-label={t.survey.star(n)}
            onClick={() => {
              setSent(n)
              post('/metrics/survey', { stars: n, context }).catch(() => undefined)
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

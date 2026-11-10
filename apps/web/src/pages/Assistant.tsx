import { useEffect, useRef, useState, type FormEvent } from 'react'
import {
  ApiError,
  api,
  askAssistant,
  post,
  type AskOption,
  type AskSource,
  type QuickAction,
} from '../api'
import { StarSurvey } from '../components/StarSurvey'
import { Alert, Button, Page, useOnline } from '../components/ui'
import { t } from '../i18n'
import { navigate } from '../router'

interface Turn {
  id: number
  question: string
  answer: string
  sources: AskSource[]
  options: AskOption[]
  interactionId: string | null
  pending: boolean
  error?: string
  feedback?: boolean
}

function Answer({ turn, onAsk, onFeedback }: { turn: Turn; onAsk: (q: string) => void; onFeedback: (useful: boolean) => void }) {
  return (
    <div className="rounded-2xl bg-white p-4 shadow-sm">
      <p className="text-sm font-semibold text-stone-600">{t.assistant.me}</p>
      {turn.error ? (
        <Alert>{turn.error}</Alert>
      ) : (
        // Texto plano: React escapa todo, nunca se interpreta HTML del modelo (SECURITY, sección 3).
        <p className="whitespace-pre-line text-lg text-stone-900">{turn.answer || (turn.pending ? t.assistant.thinking : '')}</p>
      )}
      {turn.sources.length > 0 && (
        <p className="mt-2 text-sm text-stone-700">
          {t.assistant.source}: {turn.sources.map((s) => s.label).join(' · ')}
        </p>
      )}
      {!turn.pending && turn.options.length > 0 && (
        <div className="mt-3 space-y-2">
          <p className="text-stone-700">{t.assistant.chooseOne}</p>
          {turn.options.map((o) => (
            <Button key={o.question} variant="secondary" className="w-full text-left" onClick={() => onAsk(o.question)}>
              {o.label}
            </Button>
          ))}
        </div>
      )}
      {!turn.pending && turn.interactionId && (
        <div className="mt-3 flex gap-2">
          {turn.feedback === undefined ? (
            <>
              <Button variant="secondary" aria-label={t.assistant.helpful} onClick={() => onFeedback(true)}>
                👍
              </Button>
              <Button variant="secondary" aria-label={t.assistant.notHelpful} onClick={() => onFeedback(false)}>
                👎
              </Button>
            </>
          ) : (
            <p role="status" className="text-stone-700">
              {t.assistant.thanks}
            </p>
          )}
        </div>
      )}
    </div>
  )
}

export default function Assistant() {
  const online = useOnline()
  const [quick, setQuick] = useState<QuickAction[]>([])
  const [turns, setTurns] = useState<Turn[]>([])
  const [question, setQuestion] = useState('')
  const busy = turns.some((x) => x.pending)
  const nextId = useRef(1)
  const bottom = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api<QuickAction[]>('/assistant/quick-actions')
      .then(setQuick)
      .catch(() => setQuick([]))
  }, [])

  useEffect(() => {
    bottom.current?.scrollIntoView?.({ block: 'end' })
  }, [turns])

  const update = (id: number, patch: Partial<Turn> | ((x: Turn) => Partial<Turn>)) =>
    setTurns((all) => all.map((x) => (x.id === id ? { ...x, ...(typeof patch === 'function' ? patch(x) : patch) } : x)))

  async function ask(q: string, quickAction?: string) {
    const text = q.trim()
    if (!text || busy) return
    const id = nextId.current++
    setTurns((all) => [
      ...all,
      { id, question: text, answer: '', sources: [], options: [], interactionId: null, pending: true },
    ])
    setQuestion('')
    try {
      await askAssistant({ question: text, ...(quickAction ? { quick_action: quickAction } : {}) }, (e) => {
        if (e.event === 'meta') update(id, { sources: e.data.sources, options: e.data.options })
        else if (e.event === 'delta') update(id, (x) => ({ answer: x.answer + e.data.text }))
        else if (e.event === 'replace') update(id, { answer: e.data.text })
        else
          update(id, {
            answer: e.data.answer,
            sources: e.data.sources,
            options: e.data.options,
            interactionId: e.data.interaction_id,
            pending: false,
          })
      })
    } catch (err) {
      update(id, { pending: false, error: err instanceof ApiError ? err.userMessage : t.genericError })
    }
  }

  async function feedback(turn: Turn, useful: boolean) {
    if (!turn.interactionId) return
    update(turn.id, { feedback: useful })
    try {
      await post('/assistant/feedback', { interaction_id: turn.interactionId, useful })
    } catch {
      /* el feedback es opcional: si falla, no molestamos a la usuaria */
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault()
    void ask(question)
  }

  return (
    <Page title={t.assistant.title} onBack={() => navigate('/')}>
      {!online && <Alert kind="warning">{t.assistant.offline}</Alert>}
      {turns.length === 0 && <p className="mb-4 text-lg text-stone-700">{t.assistant.intro}</p>}
      {quick.length > 0 && (
        <section aria-label={t.assistant.quick} className="mb-4 flex flex-wrap gap-2">
          {quick.map((qa) => (
            <Button key={qa.id} variant="secondary" disabled={busy || !online} onClick={() => void ask(qa.question, qa.id)}>
              {qa.label}
            </Button>
          ))}
        </section>
      )}
      <div aria-live="polite" className="space-y-4">
        {turns.map((turn) => (
          <div key={turn.id} className="space-y-2">
            <p className="ml-8 rounded-2xl bg-orange-100 p-3 text-lg text-stone-900">
              <span className="sr-only">{t.assistant.you}: </span>
              {turn.question}
            </p>
            <Answer turn={turn} onAsk={(q) => void ask(q)} onFeedback={(u) => void feedback(turn, u)} />
          </div>
        ))}
        {turns.filter((x) => !x.pending && !x.error).length >= 2 && <StarSurvey context="assistant" />}
        <div ref={bottom} />
      </div>
      <form onSubmit={submit} className="mt-6 flex gap-2">
        <label htmlFor="assistant-q" className="sr-only">
          {t.assistant.label}
        </label>
        <input
          id="assistant-q"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={t.assistant.placeholder}
          maxLength={500}
          autoComplete="off"
          className="min-h-12 min-w-0 flex-1 rounded-xl border-2 border-stone-400 px-3 text-lg focus:border-brand focus:outline-none"
        />
        <Button type="submit" className="shrink-0" disabled={busy || !online || !question.trim()}>
          {t.assistant.send}
        </Button>
      </form>
    </Page>
  )
}

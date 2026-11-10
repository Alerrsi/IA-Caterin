import { useEffect, useState, type ChangeEvent } from 'react'
import { ApiError, countPhoto, type CountOut, type RecipeSummary } from '../api'
import { DetectionOverlay } from '../components/DetectionOverlay'
import { StarSurvey } from '../components/StarSurvey'
import { Alert, Button, Field, inputClass, Page, Spinner, useOnline } from '../components/ui'
import { t } from '../i18n'
import { useCached } from '../offline/cache'
import { listPhotos, PhotoQueueFullError, removePhoto, savePhoto, type PendingPhoto } from '../offline/photos'
import { enqueue } from '../offline/queue'
import { navigate } from '../router'

/** `/recipes` también trae si la receta es un producto final (lo que se puede contar). */
type Recipe = RecipeSummary & { is_final_product?: boolean }

interface Photo {
  blob: Blob
  url: string | null
  pendingId?: string
}

interface Line {
  visionClass: string
  detected: number
  qty: number
  recipeId: string | null
  recipeName: string | null
}

type Stage = 'start' | 'counting' | 'review' | 'done'

function objectUrl(blob: Blob): string | null {
  return typeof URL.createObjectURL === 'function' ? URL.createObjectURL(blob) : null
}

const fileButton =
  'flex min-h-14 w-full cursor-pointer items-center justify-center rounded-2xl px-4 py-3 text-xl font-bold focus-within:ring-4 focus-within:ring-orange-300'

function PhotoInput({ label, capture, onFile, primary }: { label: string; capture?: boolean; onFile: (f: File) => void; primary?: boolean }) {
  const onChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (file) onFile(file)
  }
  return (
    <label
      className={`${fileButton} ${primary ? 'bg-brand text-white hover:bg-brand-dark' : 'border-2 border-brand bg-white text-brand hover:bg-orange-50'}`}
    >
      {label}
      <input
        type="file"
        accept="image/*"
        {...(capture ? { capture: 'environment' as const } : {})}
        className="sr-only"
        onChange={onChange}
      />
    </label>
  )
}

function Stepper({ name, value, onChange }: { name: string; value: number; onChange: (n: number) => void }) {
  const btn =
    'min-h-14 min-w-14 rounded-xl border-2 border-brand bg-white text-3xl font-bold text-brand focus-visible:ring-4 focus-visible:ring-orange-300 disabled:border-stone-300 disabled:text-stone-400'
  return (
    <div className="flex items-center gap-3">
      <button type="button" className={btn} aria-label={t.vision.decrease(name)} disabled={value <= 0} onClick={() => onChange(Math.max(0, value - 1))}>
        −
      </button>
      <span className="min-w-12 text-center text-3xl font-bold tabular-nums" aria-live="polite">
        {value}
      </span>
      <button type="button" className={btn} aria-label={t.vision.increase(name)} onClick={() => onChange(value + 1)}>
        +
      </button>
    </div>
  )
}

function RecipeSelect({ label, recipes, value, onChange }: { label: string; recipes: Recipe[]; value: string; onChange: (id: string) => void }) {
  return (
    <Field label={label}>
      <select className={inputClass} value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">{t.vision.chooseRecipe}</option>
        {recipes.map((r) => (
          <option key={r.id} value={r.id}>
            {r.name}
          </option>
        ))}
      </select>
    </Field>
  )
}

export default function Vision() {
  const online = useOnline()
  const recipes = useCached<Recipe[]>('recipes', '/recipes')
  const finals = (recipes.value?.data ?? []).filter((r) => r.is_active && r.is_final_product !== false)
  const [stage, setStage] = useState<Stage>('start')
  const [photo, setPhoto] = useState<Photo | null>(null)
  const [count, setCount] = useState<CountOut | null>(null)
  const [lines, setLines] = useState<Line[]>([])
  const [manualOpen, setManualOpen] = useState(false)
  const [manual, setManual] = useState({ recipeId: '', qty: '' })
  const [pending, setPending] = useState<PendingPhoto[]>([])
  const [error, setError] = useState<string | null>(null)
  const [info, setInfo] = useState<string | null>(null)
  const [doneMsg, setDoneMsg] = useState('')

  useEffect(() => {
    let alive = true
    listPhotos().then((p) => alive && setPending(p))
    return () => {
      alive = false
    }
  }, [online])

  useEffect(() => {
    const url = photo?.url
    return () => {
      if (url && typeof URL.revokeObjectURL === 'function') URL.revokeObjectURL(url)
    }
  }, [photo])

  function reset() {
    setStage('start')
    setPhoto(null)
    setCount(null)
    setLines([])
    setManualOpen(false)
    setManual({ recipeId: '', qty: '' })
    setError(null)
    setInfo(null)
  }

  async function runCount(p: Photo) {
    setPhoto(p)
    setError(null)
    setInfo(null)
    if (!online) return // queda la foto a la vista con la opción de guardarla
    setStage('counting')
    try {
      const out = await countPhoto(p.blob)
      setCount(out)
      setLines(
        out.counts.map((c) => ({
          visionClass: c.vision_class,
          detected: c.count,
          qty: c.count,
          recipeId: c.recipe_id,
          recipeName: c.recipe_name,
        })),
      )
      setStage('review')
      if (out.counts.length === 0) {
        setInfo(t.vision.noDetections)
        setManualOpen(true)
      }
    } catch (err) {
      setStage('start')
      if (err instanceof ApiError && err.status === 503) {
        setInfo(t.vision.noModel)
        setManualOpen(true)
      } else if (err instanceof ApiError && err.status === 0) {
        setInfo(t.vision.offline)
      } else {
        setError(err instanceof ApiError ? err.userMessage : t.genericError)
      }
    }
  }

  function onFile(file: File) {
    void runCount({ blob: file, url: objectUrl(file) })
  }

  async function saveForLater() {
    if (!photo) return
    try {
      await savePhoto(photo.blob)
      setPending(await listPhotos())
      reset()
      setInfo(t.vision.photoSaved)
    } catch (err) {
      setError(err instanceof PhotoQueueFullError ? t.vision.queueFull : t.genericError)
    }
  }

  async function countPending() {
    const first = pending[0]
    if (first) await runCount({ blob: first.blob, url: objectUrl(first.blob), pendingId: first.id })
  }

  async function discardPending() {
    const first = pending[0]
    if (!first) return
    await removePhoto(first.id)
    setPending(await listPhotos())
  }

  async function finish(msg: string) {
    if (photo?.pendingId) {
      await removePhoto(photo.pendingId)
      setPending(await listPhotos())
    }
    setDoneMsg(msg)
    setStage('done')
  }

  async function confirmCount() {
    if (!count) return
    if (lines.some((l) => !l.recipeId)) {
      setError(t.vision.chooseRecipe)
      return
    }
    setError(null)
    for (const l of lines) {
      const name = l.recipeName ?? l.visionClass
      await enqueue({
        path: '/vision/productions',
        body: {
          recipe_id: l.recipeId,
          confirmed_qty: l.qty,
          detected_qty: l.detected,
          model_version: count.model_version,
          detections: count.detections.filter((d) => d.vision_class === l.visionClass),
        },
        label: `${t.vision.title} · ${name}: ${l.qty}`,
      })
    }
    await finish(navigator.onLine ? t.vision.confirmed : t.vision.confirmedOffline)
  }

  async function confirmManual() {
    const qty = Number(manual.qty)
    if (!manual.recipeId) {
      setError(t.vision.chooseRecipe)
      return
    }
    if (manual.qty.trim() === '' || !Number.isInteger(qty) || qty < 0) {
      setError(t.vision.badQty)
      return
    }
    setError(null)
    const name = finals.find((r) => r.id === manual.recipeId)?.name ?? ''
    await enqueue({
      path: '/vision/productions',
      body: { recipe_id: manual.recipeId, confirmed_qty: qty },
      label: `${t.vision.title} · ${name}: ${qty}`,
    })
    await finish(navigator.onLine ? t.vision.confirmed : t.vision.confirmedOffline)
  }

  const setLine = (i: number, patch: Partial<Line>) =>
    setLines((all) => all.map((l, j) => (j === i ? { ...l, ...patch } : l)))

  if (stage === 'done') {
    return (
      <Page title={t.vision.title} onBack={() => navigate('/')}>
        <div className="space-y-4">
          <Alert kind="info">{doneMsg}</Alert>
          <StarSurvey context="vision" />
          <Button className="w-full" onClick={reset}>
            {t.vision.another}
          </Button>
        </div>
      </Page>
    )
  }

  return (
    <Page title={t.vision.title} onBack={() => navigate('/')}>
      <div className="space-y-4">
        {!online && <Alert kind="warning">{t.vision.offline}</Alert>}
        {error && <Alert>{error}</Alert>}
        {info && <Alert kind="info">{info}</Alert>}

        {pending.length > 0 && stage === 'start' && !photo && (
          <section className="rounded-2xl bg-white p-4 shadow-sm">
            <p className="mb-3 font-semibold">{t.vision.pendingPhotos(pending.length)}</p>
            <div className="flex gap-2">
              <Button className="flex-1" disabled={!online} onClick={() => void countPending()}>
                {t.vision.countNow}
              </Button>
              <Button variant="secondary" className="flex-1" onClick={() => void discardPending()}>
                {t.vision.discard}
              </Button>
            </div>
          </section>
        )}

        {stage === 'start' && !photo && (
          <>
            <p className="text-lg text-stone-700">{t.vision.intro}</p>
            <PhotoInput label={t.vision.takePhoto} capture primary onFile={onFile} />
            <PhotoInput label={t.vision.choosePhoto} onFile={onFile} />
          </>
        )}

        {stage === 'counting' && <Spinner label={t.vision.counting} />}

        {photo && stage !== 'counting' && (
          <>
            {photo.url && (
              <DetectionOverlay
                src={photo.url}
                alt={t.vision.result}
                boxes={stage === 'review' && count ? count.detections : []}
              />
            )}
            {stage === 'start' && !online && (
              <Button className="w-full" onClick={() => void saveForLater()}>
                {t.vision.savePhoto}
              </Button>
            )}
          </>
        )}

        {stage === 'review' && lines.length > 0 && (
          <section className="space-y-3">
            <h2 className="text-xl font-bold">{t.vision.result}</h2>
            {lines.map((l, i) => {
              const name = l.recipeName ?? l.visionClass
              return (
                <div key={l.visionClass} className="space-y-3 rounded-2xl bg-white p-4 shadow-sm">
                  {l.recipeName ? (
                    <p className="text-lg font-bold">{l.recipeName}</p>
                  ) : (
                    <>
                      <p className="font-semibold text-stone-800">{t.vision.unknownProduct(l.visionClass)}</p>
                      <RecipeSelect
                        label={t.vision.product}
                        recipes={finals}
                        value={l.recipeId ?? ''}
                        onChange={(id) =>
                          setLine(i, { recipeId: id || null, recipeName: finals.find((r) => r.id === id)?.name ?? null })
                        }
                      />
                    </>
                  )}
                  <p className="text-stone-700">{t.vision.detected(l.detected)}</p>
                  <Stepper name={name} value={l.qty} onChange={(qty) => setLine(i, { qty })} />
                </div>
              )
            })}
            <Button className="w-full" onClick={() => void confirmCount()}>
              {t.vision.confirm}
            </Button>
          </section>
        )}

        {(stage === 'start' || stage === 'review') && (
          <section className="rounded-2xl bg-white p-4 shadow-sm">
            {manualOpen ? (
              <div className="space-y-3">
                <h2 className="text-xl font-bold">{t.vision.manualTitle}</h2>
                <RecipeSelect
                  label={t.vision.product}
                  recipes={finals}
                  value={manual.recipeId}
                  onChange={(recipeId) => setManual((m) => ({ ...m, recipeId }))}
                />
                <Field label={t.vision.qty}>
                  <input
                    className={inputClass}
                    inputMode="numeric"
                    value={manual.qty}
                    onChange={(e) => setManual((m) => ({ ...m, qty: e.target.value.replace(/\D/g, '') }))}
                  />
                </Field>
                <Button className="w-full" onClick={() => void confirmManual()}>
                  {t.vision.confirm}
                </Button>
              </div>
            ) : (
              <Button variant="secondary" className="w-full" onClick={() => setManualOpen(true)}>
                {t.vision.manual}
              </Button>
            )}
          </section>
        )}

        {photo && stage === 'start' && (
          <Button variant="ghost" onClick={reset}>
            {t.vision.another}
          </Button>
        )}
      </div>
    </Page>
  )
}

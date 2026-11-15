import { useId, useRef, useState } from 'react'
import { ApiError } from '../api'
import { t } from '../i18n'
import { Alert, Button } from './ui'
import { Icon } from './Icon'

const MAX_BYTES = 2 * 1024 * 1024 // igual que MEDIA_MAX_UPLOAD_MB de la API (ADR-009)

/**
 * Elegir, cambiar o quitar una imagen del catálogo (logo de la pyme o foto de producto). Avisa antes de subir si pesa
 * más de 2 MB; la API la re-codifica y le quita la ubicación y otros metadatos.
 */
export function ImagePicker({
  label,
  url,
  onUpload,
  onRemove,
  disabled = false,
  square = false,
}: {
  label: string
  url: string | null | undefined
  onUpload: (file: File) => Promise<void>
  onRemove: () => Promise<void>
  disabled?: boolean
  square?: boolean
}) {
  const input = useRef<HTMLInputElement>(null)
  const id = useId()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function run(action: () => Promise<void>) {
    setBusy(true)
    setError(null)
    try {
      await action()
    } catch (err) {
      setError(err instanceof ApiError ? err.userMessage : t.genericError)
    } finally {
      setBusy(false)
    }
  }

  function pick(file: File | undefined) {
    if (input.current) input.current.value = ''
    if (!file) return
    if (file.size > MAX_BYTES) return setError(t.catalogAdmin.tooBig)
    void run(() => onUpload(file))
  }

  return (
    <div>
      <p id={`${id}-label`} className="mb-2 font-medium text-on-surface">
        {label}
      </p>
      <div className="flex items-center gap-4">
        {url ? (
          <img src={url} alt="" className={`shrink-0 rounded-xl object-cover ${square ? 'h-20 w-20' : 'h-20 w-28'}`} />
        ) : (
          <span
            className={`inline-flex shrink-0 items-center justify-center rounded-xl bg-surface-container-high text-on-surface-variant ${square ? 'h-20 w-20' : 'h-20 w-28'}`}
          >
            <Icon name="photo" className="h-8 w-8" />
          </span>
        )}
        <div className="flex flex-wrap gap-2">
          <input
            ref={input}
            id={`${id}-file`}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="sr-only"
            aria-labelledby={`${id}-label`}
            onChange={(e) => pick(e.target.files?.[0])}
            disabled={disabled || busy}
          />
          <Button variant="secondary" onClick={() => input.current?.click()} disabled={disabled || busy}>
            {busy ? t.catalogAdmin.uploading : url ? t.catalogAdmin.change : t.catalogAdmin.choose}
          </Button>
          {url && (
            <Button variant="ghost" onClick={() => run(onRemove)} disabled={disabled || busy}>
              {t.catalogAdmin.remove}
            </Button>
          )}
        </div>
      </div>
      <p className="mt-2 text-sm text-on-surface-variant">{t.catalogAdmin.imageHint}</p>
      {error && (
        <div className="mt-2">
          <Alert>{error}</Alert>
        </div>
      )}
    </div>
  )
}

/**
 * Fotos de producción guardadas sin señal (ADR-004, punto 6): se comprimen (≤ 1280 px, JPEG ~80 %) y se
 * cuentan al volver la red. Tope de 20 fotos para no llenar el teléfono. Se guardan por pyme (src/offline/db.ts).
 */
import { getItem, setItem, uuid } from './db'

export interface PendingPhoto {
  id: string
  blob: Blob
  createdAt: string
}

const KEY = 'photos:pending'
export const MAX_PHOTOS = 20
const MAX_SIDE = 1280
const QUALITY = 0.8

export class PhotoQueueFullError extends Error {}

/** Achica la foto. Si el navegador no puede (sin canvas o sin createImageBitmap), guarda el original. */
export async function compress(blob: Blob): Promise<Blob> {
  if (typeof createImageBitmap !== 'function' || typeof document === 'undefined') return blob
  try {
    const bmp = await createImageBitmap(blob)
    const scale = Math.min(1, MAX_SIDE / Math.max(bmp.width, bmp.height))
    const canvas = document.createElement('canvas')
    canvas.width = Math.round(bmp.width * scale)
    canvas.height = Math.round(bmp.height * scale)
    const ctx = canvas.getContext('2d')
    if (!ctx) return blob
    ctx.drawImage(bmp, 0, 0, canvas.width, canvas.height)
    bmp.close?.()
    const out = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', QUALITY))
    return out && out.size < blob.size ? out : blob
  } catch {
    return blob
  }
}

export async function listPhotos(): Promise<PendingPhoto[]> {
  return (await getItem<PendingPhoto[]>(KEY)) ?? []
}

export async function savePhoto(blob: Blob): Promise<PendingPhoto> {
  const current = await listPhotos()
  if (current.length >= MAX_PHOTOS) throw new PhotoQueueFullError()
  const photo: PendingPhoto = { id: uuid(), blob: await compress(blob), createdAt: new Date().toISOString() }
  await setItem(KEY, [...current, photo])
  return photo
}

export async function removePhoto(id: string): Promise<void> {
  await setItem(
    KEY,
    (await listPhotos()).filter((p) => p.id !== id),
  )
}

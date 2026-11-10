/**
 * Almacenamiento local de la PWA (ADR-004): IndexedDB con una sola tabla clave → valor.
 * Las claves van con el id de la pyme como prefijo, para que dos cuentas en el mismo teléfono no se mezclen.
 * Sin IndexedDB (pruebas en jsdom o navegadores muy viejos) usa memoria: la app funciona, pero sin persistir.
 */

const DB_NAME = 'caterin'
const STORE = 'kv'
const memory = new Map<string, unknown>()
let dbPromise: Promise<IDBDatabase> | null = null
let scope = 'anon'

export function setScope(pymeId: string | null): void {
  scope = pymeId ?? 'anon'
}

function key(name: string): string {
  return `${scope}:${name}`
}

function open(): Promise<IDBDatabase> | null {
  if (typeof indexedDB === 'undefined') return null
  if (!dbPromise) {
    dbPromise = new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, 1)
      req.onupgradeneeded = () => req.result.createObjectStore(STORE)
      req.onsuccess = () => resolve(req.result)
      req.onerror = () => reject(req.error)
    })
  }
  return dbPromise
}

async function run<T>(mode: IDBTransactionMode, fn: (s: IDBObjectStore) => IDBRequest): Promise<T> {
  const db = await open()!
  return new Promise<T>((resolve, reject) => {
    const req = fn(db.transaction(STORE, mode).objectStore(STORE))
    req.onsuccess = () => resolve(req.result as T)
    req.onerror = () => reject(req.error)
  })
}

export async function getItem<T>(name: string): Promise<T | undefined> {
  if (!open()) return memory.get(key(name)) as T | undefined
  try {
    return await run<T | undefined>('readonly', (s) => s.get(key(name)))
  } catch {
    return memory.get(key(name)) as T | undefined
  }
}

export async function setItem(name: string, value: unknown): Promise<void> {
  memory.set(key(name), value)
  if (!open()) return
  try {
    await run('readwrite', (s) => s.put(value, key(name)))
  } catch {
    /* sin espacio o modo privado: queda en memoria */
  }
}

export async function removeItem(name: string): Promise<void> {
  memory.delete(key(name))
  if (!open()) return
  try {
    await run('readwrite', (s) => s.delete(key(name)))
  } catch {
    /* nada que hacer */
  }
}

/** Solo para pruebas. */
export function resetMemory(): void {
  memory.clear()
}

/** UUID v4 también fuera de HTTPS (crypto.randomUUID solo existe en contextos seguros). */
export function uuid(): string {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  const b = crypto.getRandomValues(new Uint8Array(16))
  b[6] = (b[6] & 0x0f) | 0x40
  b[8] = (b[8] & 0x3f) | 0x80
  const h = Array.from(b, (x) => x.toString(16).padStart(2, '0')).join('')
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`
}

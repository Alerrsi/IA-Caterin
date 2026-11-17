/**
 * Buscador global "¿Qué necesitas?" (T22): funciones puras para encontrar acciones y datos sin tildes, con
 * coincidencia aproximada y sin IA. La pantalla (`components/QuickFind.tsx`) arma los candidatos desde lo guardado en
 * el teléfono, así funciona sin red.
 */

export type FindGroup = 'actions' | 'ingredients' | 'recipes' | 'products' | 'orders' | 'pymes' | 'catalog'

export interface FindItem {
  id: string
  group: FindGroup
  label: string
  /** Texto chico bajo el nombre (stock, fecha, pyme…). */
  detail?: string
  /** Ruta de la app a la que lleva. */
  path: string
  /** Palabras extra que también encuentran el elemento (sinónimos de una acción, cliente de un pedido…). */
  keywords?: string
}

export interface FindResult extends FindItem {
  score: number
}

/** Orden de los grupos en la lista de resultados. */
export const GROUP_ORDER: FindGroup[] = ['actions', 'ingredients', 'recipes', 'products', 'orders', 'pymes', 'catalog']

export const MAX_RESULTS = 8
const PER_GROUP = 5

/** "Ají de Color " -> "aji de color" */
export function normalize(text: string): string {
  return text
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9ñ\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

/** Distancia de edición con tope: deja de contar al pasar `max` (barata para palabras cortas). */
export function editDistance(a: string, b: string, max: number): number {
  if (Math.abs(a.length - b.length) > max) return max + 1
  let prev = Array.from({ length: b.length + 1 }, (_, j) => j)
  for (let i = 1; i <= a.length; i++) {
    const cur = [i]
    let best = i
    for (let j = 1; j <= b.length; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1
      cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
      best = Math.min(best, cur[j])
    }
    if (best > max) return max + 1
    prev = cur
  }
  return prev[b.length]
}

/** Qué tan bien calza una palabra buscada con una palabra del texto (0 = no calza). */
function wordScore(q: string, word: string, inside = true): number {
  if (word === q) return 10
  if (word.startsWith(q)) return 8
  if (inside && q.length >= 3 && word.includes(q)) return 5
  // Error de tipeo: una letra de diferencia desde 4 letras, dos desde 7 ("arina" encuentra "harina").
  if (q.length >= 4) {
    const max = q.length >= 7 ? 2 : 1
    const target = word.length > q.length ? word.slice(0, q.length + 1) : word
    if (editDistance(q, target, max) <= max || editDistance(q, word, max) <= max) return 3
  }
  return 0
}

/**
 * Puntaje de un elemento para la consulta. Todas las palabras buscadas deben calzar con alguna palabra del nombre o
 * de las palabras clave; el nombre pesa más que las palabras clave. 0 = no aparece.
 */
export function scoreItem(query: string, item: FindItem): number {
  const qWords = normalize(query).split(' ').filter(Boolean)
  if (qWords.length === 0) return 0
  const nameWords = normalize(item.label).split(' ').filter(Boolean)
  const extraWords = normalize(item.keywords ?? '').split(' ').filter(Boolean)
  let total = 0
  for (const q of qWords) {
    const inName = Math.max(0, ...nameWords.map((w) => wordScore(q, w)))
    // En las palabras clave no cuenta un trozo en medio ("emp" no debe encontrar "tiempo").
    const inExtra = Math.max(0, ...extraWords.map((w) => wordScore(q, w, false))) * 0.6
    const best = Math.max(inName, inExtra)
    if (best === 0) return 0
    total += best
  }
  // Un nombre que empieza igual que la consulta completa va primero ("emp" -> "Empanadas…").
  if (normalize(item.label).startsWith(normalize(query))) total += 4
  return total
}

/**
 * Busca en los candidatos y devuelve como máximo `MAX_RESULTS`, ordenados por grupo y, dentro del grupo, por puntaje.
 * Sin consulta, devuelve las acciones sugeridas (las primeras `MAX_RESULTS`).
 */
export function search(query: string, items: FindItem[], max = MAX_RESULTS): FindResult[] {
  if (normalize(query) === '') {
    return items
      .filter((i) => i.group === 'actions')
      .slice(0, max)
      .map((i) => ({ ...i, score: 0 }))
  }
  const ranked = items
    .map((i) => ({ ...i, score: scoreItem(query, i) }))
    .filter((i) => i.score > 0)
    .sort(
      (a, b) =>
        b.score - a.score ||
        GROUP_ORDER.indexOf(a.group) - GROUP_ORDER.indexOf(b.group) ||
        a.label.localeCompare(b.label, 'es'),
    )
  // Variedad: como máximo PER_GROUP por grupo mientras haya de otros grupos; si sobran espacios, se completan.
  const picked: FindResult[] = []
  const perGroup = new Map<FindGroup, number>()
  for (const r of ranked) {
    if (picked.length >= max) break
    const n = perGroup.get(r.group) ?? 0
    if (n >= PER_GROUP) continue
    perGroup.set(r.group, n + 1)
    picked.push(r)
  }
  for (const r of ranked) {
    if (picked.length >= max) break
    if (!picked.includes(r)) picked.push(r)
  }
  return picked.sort(
    (a, b) => GROUP_ORDER.indexOf(a.group) - GROUP_ORDER.indexOf(b.group) || b.score - a.score,
  )
}

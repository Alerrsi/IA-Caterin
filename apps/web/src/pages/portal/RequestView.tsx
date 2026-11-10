import { useEffect, useState } from 'react'
import { api, apiBlob, ApiError, post, type PortalRequest } from '../../api'
import { useAuth } from '../../auth'
import { Alert, Button, Page, Spinner, StatusChip } from '../../components/ui'
import { formatCLP, formatDate } from '../../format'
import { t } from '../../i18n'
import { navigate } from '../../router'

/** Una cotización guardada del cliente: precio, PDF, enviar a la pyme y su respuesta (ADR-007). */
export default function RequestView({ id }: { id: string }) {
  const { pyme } = useAuth()
  const [req, setReq] = useState<PortalRequest | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  const fail = (err: unknown) => setError(err instanceof ApiError ? err.userMessage : t.genericError)

  useEffect(() => {
    api<PortalRequest>(`/portal/requests/${id}`).then(setReq).catch(fail)
  }, [id])

  async function act(action: 'send' | 'cancel' | 'quote') {
    if (action === 'cancel' && !window.confirm(t.portal.cancelConfirm)) return
    setBusy(action)
    setError(null)
    try {
      setReq(await post<PortalRequest>(`/portal/requests/${id}/${action}`, {}))
    } catch (err) {
      fail(err)
    } finally {
      setBusy(null)
    }
  }

  async function openPdf() {
    setBusy('pdf')
    setError(null)
    const win = window.open('', '_blank') // antes de esperar: los navegadores móviles bloquean popups tardíos
    try {
      const url = URL.createObjectURL(await apiBlob(`/portal/requests/${id}/pdf`))
      if (win) win.location.href = url
      else window.location.href = url
    } catch (err) {
      win?.close()
      fail(err)
    } finally {
      setBusy(null)
    }
  }

  if (!req) {
    return (
      <Page title={t.portal.requestTitle} onBack={() => navigate('/')}>
        {error ? <Alert>{error}</Alert> : <Spinner label={t.loading} />}
      </Page>
    )
  }

  const q = req.quote
  return (
    <Page title={t.portal.requestTitle} onBack={() => navigate('/')}>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <StatusChip status={req.status}>{t.portal.status[req.status]}</StatusChip>
        {req.event_date && <span className="text-stone-700">{t.portal.eventDate(formatDate(req.event_date))}</span>}
        {req.guests && <span className="text-stone-700">· {t.portal.guests(req.guests)}</span>}
      </div>

      {req.owner_message && (
        <div className="mb-4">
          <Alert kind="info">
            <p className="font-semibold">{t.portal.ownerMessage}</p>
            <p>{req.owner_message}</p>
          </Alert>
        </div>
      )}
      {req.status === 'customer_draft' && (
        <div className="mb-4">
          <Alert kind="info">{t.portal.savedHint}</Alert>
        </div>
      )}
      {req.status === 'requested' && (
        <div className="mb-4">
          <Alert kind="info">{t.portal.sentInfo}</Alert>
        </div>
      )}
      {req.price_pending && (
        <div className="mb-4">
          <Alert kind="warning">{t.portal.pending[req.price_pending]}</Alert>
        </div>
      )}

      {q?.is_complete && (
        <section className="rounded-2xl bg-white p-5 shadow-sm" aria-label={t.view.total}>
          <p className="text-stone-700">{t.view.total}</p>
          <p className="text-4xl font-bold text-stone-900" data-testid="request-total">
            {formatCLP(q.total_clp)}
          </p>
          <dl className="mt-3 grid grid-cols-2 gap-1 text-stone-800">
            <dt>{t.view.net}</dt>
            <dd className="text-right">{formatCLP(q.net_clp)}</dd>
            <dt>{t.view.vat(q.vat_pct)}</dt>
            <dd className="text-right">{formatCLP(q.vat_clp)}</dd>
          </dl>
          {q.valid_until && <p className="mt-2 text-sm text-stone-600">{t.view.validUntil(formatDate(q.valid_until))}</p>}
        </section>
      )}

      <h2 className="mb-2 mt-6 text-xl font-bold">{t.view.products}</h2>
      <ul className="divide-y divide-stone-200 rounded-2xl bg-white shadow-sm">
        {(q?.products ?? req.lines.map((l) => ({ ...l, unit_price_clp: null, subtotal_clp: null }))).map((p, i) => (
          <li key={i} className="flex items-start justify-between gap-3 p-4">
            <div>
              <p className="font-semibold">{p.name}</p>
              <p className="text-stone-700">
                {p.qty} {p.unit_label}
                {p.unit_price_clp !== null && ` · ${formatCLP(p.unit_price_clp)} ${t.view.unitPrice}`}
              </p>
            </div>
            <p className="font-semibold">{p.subtotal_clp === null ? '—' : formatCLP(p.subtotal_clp)}</p>
          </li>
        ))}
      </ul>
      {req.notes && <p className="mt-2 text-stone-700">{t.orders.customerNotes(req.notes)}</p>}

      {error && (
        <div className="mt-4">
          <Alert>{error}</Alert>
        </div>
      )}

      <div className="mt-6 space-y-3">
        {req.can_send && (
          <Button className="w-full" onClick={() => act('send')} disabled={busy !== null}>
            {busy === 'send' ? t.portal.sending : t.portal.send(pyme?.name ?? '')}
          </Button>
        )}
        {q?.is_complete && (
          <Button variant="secondary" className="w-full" onClick={openPdf} disabled={busy !== null}>
            {busy === 'pdf' ? t.view.pdfLoading : t.portal.pdf}
          </Button>
        )}
        {req.can_send && (
          <Button variant="secondary" className="w-full" onClick={() => act('quote')} disabled={busy !== null}>
            {t.portal.requote}
          </Button>
        )}
        {req.can_cancel && (
          <Button variant="ghost" className="w-full" onClick={() => act('cancel')} disabled={busy !== null}>
            {t.portal.cancel}
          </Button>
        )}
      </div>
    </Page>
  )
}

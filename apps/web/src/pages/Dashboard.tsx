import { useState, type ReactNode } from 'react'
import type { Dashboard as DashboardData } from '../api'
import { useAuth } from '../auth'
import { BarList, ColumnChart, Meter, StatTile, TableView } from '../components/charts'
import { Alert, Button, Cells, Page, Spinner } from '../components/ui'
import { formatCLP, formatCLPCompact, formatDay, formatInt, formatMonth, formatPct, formatStock } from '../format'
import { t } from '../i18n'
import { useCached } from '../offline/cache'
import { navigate } from '../router'
import { savedAtLabel } from './Inventory'

type Months = '3' | '6' | '12'
const MONTHS: Months[] = ['3', '6', '12']
const C1 = 'var(--color-chart-1)'
const C2 = 'var(--color-chart-2)'
const d = t.dashboard

function ChartCard({ title, hint, children, className = '' }: { title: string; hint?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section aria-label={title} className={`min-w-0 rounded-xl border border-hairline bg-surface-container-lowest p-4 md:p-5 ${className}`}>
      <h2 className="font-display text-xl text-on-surface">{title}</h2>
      {hint && <p className="mb-3 mt-1 text-sm text-on-surface-variant">{hint}</p>}
      {children}
    </section>
  )
}

function Empty({ children }: { children: ReactNode }) {
  return <p className="grid-paper rounded-xl border border-dashed border-outline-variant p-5 text-on-surface-variant">{children}</p>
}

/** Filtro del periodo: una sola fila, arriba de todo lo que acota (skill dataviz). */
function PeriodPicker({ value, onChange }: { value: Months; onChange: (m: Months) => void }) {
  return (
    <div role="group" aria-label={d.period} className="inline-flex rounded-lg border border-outline bg-surface-container-lowest p-0.5">
      {MONTHS.map((m) => (
        <button
          key={m}
          type="button"
          aria-pressed={value === m}
          onClick={() => onChange(m)}
          className={`min-h-11 rounded-md px-4 text-base font-medium transition-colors focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/30 ${
            value === m ? 'bg-primary text-on-primary' : 'text-on-surface hover:bg-on-surface/8'
          }`}
        >
          {d.periods[m]}
        </button>
      ))}
    </div>
  )
}

function SalesChart({ data }: { data: DashboardData }) {
  const months = data.sales_by_month
  if (data.kpis.sold_orders === 0) return <Empty>{d.noSales}</Empty>
  const best = months.reduce((bi, m, i) => (m.net_clp > months[bi].net_clp ? i : bi), 0)
  return (
    <>
      <ColumnChart
        label={d.salesChart}
        categories={months.map((m) => ({ key: m.month, label: formatMonth(m.month), title: formatMonth(m.month, true) }))}
        series={[
          { name: d.cost, color: C2, values: months.map((m) => m.ingredients_cost_clp) },
          { name: d.marginShort, color: C1, values: months.map((m) => m.margin_clp) },
        ]}
        format={formatCLP}
        axisFormat={formatCLPCompact}
        highlight={best}
        extra={(i) => (
          <>
            <p>
              <span className="num text-on-surface">{formatCLP(months[i].net_clp)}</span> {d.netInline} ·{' '}
              <span className="num text-on-surface">{formatCLP(months[i].total_clp)}</span> {d.totalInline}
            </p>
            <p>{d.ordersN(months[i].orders)}</p>
          </>
        )}
      />
      <TableView
        caption={d.salesChart}
        head={[d.month, d.ordersCol, d.cost, d.marginShort, d.net, d.total]}
        rows={months.map((m) => [
          formatMonth(m.month, true),
          m.orders,
          formatCLP(m.ingredients_cost_clp),
          formatCLP(m.margin_clp),
          formatCLP(m.net_clp),
          formatCLP(m.total_clp),
        ])}
      />
    </>
  )
}

function UpcomingChart({ data }: { data: DashboardData }) {
  const days = data.upcoming_by_day
  if (days.every((x) => x.confirmed + x.pending === 0)) return <Empty>{d.noUpcoming}</Empty>
  return (
    <>
      <ColumnChart
        label={d.upcomingChart}
        height={180}
        categories={days.map((x) => ({ key: x.day, label: formatDay(x.day).short, title: formatDay(x.day).long }))}
        series={[
          { name: d.confirmed, color: C1, values: days.map((x) => x.confirmed) },
          { name: d.pending, color: C2, values: days.map((x) => x.pending) },
        ]}
        format={formatInt}
        extra={(i) => <p>{d.guests(days[i].guests)}</p>}
      />
      <TableView
        caption={d.upcomingChart}
        head={[d.day, d.confirmed, d.pending, d.guestsCol]}
        rows={days.map((x) => [formatDay(x.day).long, x.confirmed, x.pending, formatInt(x.guests)])}
      />
    </>
  )
}

export default function Dashboard() {
  const { user } = useAuth()
  const owner = user?.role === 'owner'
  const [months, setMonths] = useState<Months>('6')
  const { value, error, loading } = useCached<DashboardData>(`dashboard:${months}`, owner ? `/dashboard?months=${months}` : null)

  if (!owner) {
    return (
      <Page title={d.title} onBack={() => navigate('/')}>
        <Alert>{d.ownerOnly}</Alert>
      </Page>
    )
  }

  const data = value?.data
  const k = data?.kpis
  return (
    <Page title={d.title} description={d.intro} onBack={() => navigate('/')}>
      <div className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-2">
        <PeriodPicker value={months} onChange={setMonths} />
        {data && (
          <p className="text-sm text-on-surface-variant" data-testid="dashboard-period">
            {d.periodLabel(formatMonth(data.sales_by_month[0].month, true), formatMonth(data.sales_by_month.at(-1)!.month, true))}{' '}
            {d.currentMonthNote}
          </p>
        )}
      </div>

      {value?.fromCache && (
        <div className="mb-3">
          <Alert kind="info">{t.sync.staleData(savedAtLabel(value.savedAt))}</Alert>
        </div>
      )}
      {error && !data && <Alert>{error.userMessage}</Alert>}
      {!data && !error && <Spinner label={t.loading} />}

      {data && k && (
        // Mientras recarga otro periodo, se mantiene el dibujo anterior atenuado: sin saltos ni parpadeos.
        <div className={`space-y-4 transition-opacity duration-150 motion-reduce:transition-none ${loading ? 'opacity-60' : ''}`}>
          {k.pending_requests > 0 && (
            <Alert kind="info">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span>{d.requests(k.pending_requests)}</span>
                <Button variant="secondary" onClick={() => navigate('/pedidos')}>
                  {d.seeRequests}
                </Button>
              </div>
            </Alert>
          )}

          <Cells label={d.title} className="grid-cols-2 lg:grid-cols-5">
            <StatTile hero label={d.sales} value={formatCLP(k.sales_total_clp)} hint={d.salesHint(k.sold_orders)} />
            <StatTile
              className="col-span-2 lg:col-span-1"
              label={d.margin}
              value={formatCLP(k.margin_clp)}
              hint={k.margin_pct === null ? undefined : d.marginHint(formatPct(k.margin_pct))}
            />
            <StatTile label={d.orders} value={formatInt(k.sold_orders)} hint={d.ordersHint} />
            <StatTile label={d.ticket} value={formatCLP(k.avg_ticket_clp)} hint={d.ticketHint} />
          </Cells>
          {k.orders_without_quote > 0 && <Alert kind="warning">{d.withoutQuote(k.orders_without_quote)}</Alert>}

          <div className="grid gap-4 lg:grid-cols-2">
            <ChartCard title={d.salesChart} hint={d.salesChartHint} className="lg:col-span-2">
              <SalesChart data={data} />
            </ChartCard>

            <ChartCard title={d.upcomingChart} hint={d.upcomingChartHint(k.upcoming_7d)}>
              <UpcomingChart data={data} />
            </ChartCard>

            <ChartCard title={d.lowChart} hint={k.low_stock > 0 ? d.lowChartHint(k.low_stock) : undefined}>
              {data.low_stock.items.length === 0 ? (
                <Empty>{d.noLow}</Empty>
              ) : (
                <ul className="space-y-3" aria-label={d.lowChart}>
                  {data.low_stock.items.map((i) => (
                    <li key={i.ingredient_id}>
                      <Meter
                        label={i.name}
                        pct={i.pct_of_min}
                        detail={d.lowRow(formatStock(i.stock_qty, i.base_unit), formatStock(i.min_stock_qty, i.base_unit))}
                        href={`#/inventario/${i.ingredient_id}`}
                      />
                    </li>
                  ))}
                </ul>
              )}
              {k.low_stock > data.low_stock.items.length && (
                <Button variant="ghost" className="mt-2" onClick={() => navigate('/inventario')}>
                  {d.seeInventory}
                </Button>
              )}
            </ChartCard>

            <ChartCard title={d.productsChart} hint={d.productsChartHint}>
              {data.top_products.items.length === 0 ? (
                <Empty>{d.noProducts}</Empty>
              ) : (
                <BarList
                  label={d.productsChart}
                  rows={data.top_products.items.map((p) => ({
                    key: p.recipe_id,
                    label: p.name,
                    value: Number(p.units),
                    valueLabel: d.units(formatInt(Number(p.units))),
                    detail: d.ordersN(p.orders),
                    href: `#/recetas/${p.recipe_id}`,
                  }))}
                />
              )}
              {data.top_products.excluded_lines > 0 && (
                <p className="mt-3 text-sm text-on-surface-variant">{d.excluded(data.top_products.excluded_lines)}</p>
              )}
            </ChartCard>

            <ChartCard title={d.statusChart} hint={d.statusChartHint}>
              <BarList
                label={d.statusChart}
                rows={data.orders_by_status.map((s) => ({
                  key: s.status,
                  label: t.orders.status[s.status] ?? s.status,
                  value: s.orders,
                  valueLabel: formatInt(s.orders),
                }))}
              />
            </ChartCard>

            <ChartCard title={d.suppliersChart} hint={d.suppliersChartHint} className="lg:col-span-2">
              {data.spend_by_supplier.length === 0 ? (
                <Empty>{d.noSuppliers}</Empty>
              ) : (
                <BarList
                  label={d.suppliersChart}
                  rows={data.spend_by_supplier.map((s) => ({
                    key: s.supplier_id ?? 'otros',
                    label: s.supplier_id ? s.name : d.others,
                    value: s.amount_clp,
                    valueLabel: formatCLP(s.amount_clp),
                  }))}
                />
              )}
            </ChartCard>
          </div>
        </div>
      )}
    </Page>
  )
}

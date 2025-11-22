import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../../api/client'
import { ColumnChart } from '../../components/charts/ColumnChart'
import { Legend } from '../../components/charts/Legend'
import { LineChart } from '../../components/charts/LineChart'
import { shortDate } from '../../components/charts/scale'
import { timeAgo } from '../../components/format'
import { Card, EmptyState, ErrorState, Loading, PageHeader, cx } from '../../components/ui'

interface Day {
  day: string
  calls: number
  errors: number
  cost_usd: number
  input_tokens: number
  output_tokens: number
  latency_p50_ms: number | null
  latency_p95_ms: number | null
}

interface Overview {
  days: number
  totals: { calls: number; errors: number; error_rate: number | null; input_tokens: number; output_tokens: number; cost_usd: number; latency_p50_ms: number | null; latency_p95_ms: number | null }
  daily: Day[]
  by_model: { model: string; calls: number; cost_usd: number }[]
  by_status: Record<string, number>
  drafts: {
    total: number
    by_status: Record<string, number>
    evidence_gate_refusals: number
    published: number
    published_unedited: number
    drafts_with_removed_citations: number
    avg_citations_per_answer: number | null
    retrieval_p50_ms: number | null
    retrieval_p95_ms: number | null
  }
  recent_failures: { created_at: string; status: string; model: string; error: string | null; latency_ms: number }[]
}

const RANGES = [7, 14, 30, 90]
const compact = new Intl.NumberFormat(undefined, { notation: 'compact', maximumFractionDigits: 1 })
const usd = (v: number) => (v === 0 ? '$0' : v < 0.01 ? `$${v.toFixed(4)}` : v < 100 ? `$${v.toFixed(2)}` : `$${compact.format(v)}`)
const ms = (v: number | null) => (v == null ? '—' : v < 1000 ? `${Math.round(v)} ms` : `${(v / 1000).toFixed(1)} s`)
const pct = (v: number | null) => (v == null ? '—' : `${(v * 100).toFixed(v < 0.1 && v > 0 ? 1 : 0)}%`)

function StatTile({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <Card className="p-4">
      <p className="text-sm text-[var(--viz-ink-2)]">{label}</p>
      <p className="mt-1 text-xl font-semibold text-[var(--viz-ink)] sm:text-2xl">{value}</p>
      {note && <p className="mt-0.5 text-xs text-[var(--viz-muted)]">{note}</p>}
    </Card>
  )
}

function ChartCard({ title, subtitle, legend, children }: { title: string; subtitle?: string; legend?: React.ReactNode; children: React.ReactNode }) {
  return (
    <Card className="min-w-0 p-4">
      <h2 className="text-sm font-semibold text-[var(--viz-ink)]">{title}</h2>
      {subtitle && <p className="text-xs text-[var(--viz-muted)]">{subtitle}</p>}
      {legend && <div className="mt-2">{legend}</div>}
      <div className="mt-3">{children}</div>
    </Card>
  )
}

export function DashboardPage() {
  const [days, setDays] = useState(14)
  const [showTable, setShowTable] = useState(false)
  const q = useQuery({ queryKey: ['metrics', days], queryFn: () => api<Overview>(`/metrics/overview?days=${days}`), placeholderData: keepPreviousData, refetchInterval: 60_000 })

  return (
    <>
      <PageHeader title="Usage & cost" description="Every model call is logged with latency, tokens and cost. Drafts show how answers end up." />
      <div className="mb-4 flex gap-1" role="group" aria-label="Date range">
        {RANGES.map((r) => (
          <button
            key={r}
            onClick={() => setDays(r)}
            aria-pressed={days === r}
            className={cx('rounded-md px-3 py-1.5 text-sm font-medium', days === r ? 'bg-white shadow-xs ring-1 ring-slate-200' : 'text-slate-600 hover:bg-slate-100')}
          >
            <span className="hidden sm:inline">Last </span>
            {r} days
          </button>
        ))}
      </div>
      {q.isPending ? (
        <Loading />
      ) : q.isError ? (
        <ErrorState error={q.error} onRetry={() => void q.refetch()} />
      ) : (
        <div className={cx('space-y-4 transition-opacity', q.isPlaceholderData && 'opacity-60')}>
          <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
            <StatTile label="Model calls" value={compact.format(q.data.totals.calls)} note={`${compact.format(q.data.totals.input_tokens)} in · ${compact.format(q.data.totals.output_tokens)} out tokens`} />
            <StatTile label="Model cost" value={usd(q.data.totals.cost_usd)} note={q.data.totals.calls ? `${usd(q.data.totals.cost_usd / q.data.totals.calls)} per call` : undefined} />
            <StatTile label="Generation latency p95" value={ms(q.data.totals.latency_p95_ms)} note={`p50 ${ms(q.data.totals.latency_p50_ms)}`} />
            <StatTile label="Failed calls" value={pct(q.data.totals.error_rate)} note={`${q.data.totals.errors} of ${q.data.totals.calls}`} />
          </div>

          {q.data.totals.calls === 0 && q.data.drafts.total === 0 ? (
            <EmptyState title="No activity in this range">Request a draft on a ticket to see usage here.</EmptyState>
          ) : (
            <>
              <div className="grid gap-4 lg:grid-cols-2">
                <ChartCard
                  title="Model calls per day"
                  legend={<Legend kind="rect" items={[{ label: 'Succeeded', color: 'var(--viz-series-1)' }, { label: 'Failed', color: 'var(--viz-critical)', icon: '✕' }]} />}
                >
                  <ColumnChart
                    label="Model calls per day, succeeded and failed"
                    data={q.data.daily.map((d) => ({ day: d.day, ok: d.calls - d.errors, failed: d.errors }))}
                    series={[
                      { key: 'ok', label: 'succeeded', color: 'var(--viz-series-1)' },
                      { key: 'failed', label: 'failed', color: 'var(--viz-critical)' },
                    ]}
                    format={(v) => compact.format(v)}
                  />
                </ChartCard>
                <ChartCard title="Generation latency" subtitle="Successful calls, per day" legend={<Legend kind="line" items={[{ label: 'p50', color: 'var(--viz-series-1)' }, { label: 'p95', color: 'var(--viz-series-2)' }]} />}>
                  <LineChart
                    label="Generation latency p50 and p95 per day"
                    data={q.data.daily as unknown as Record<string, unknown>[]}
                    series={[
                      { key: 'latency_p50_ms', label: 'p50', color: 'var(--viz-series-1)' },
                      { key: 'latency_p95_ms', label: 'p95', color: 'var(--viz-series-2)' },
                    ]}
                    format={(v) => ms(v)}
                  />
                </ChartCard>
              </div>
              <div className="grid gap-4 lg:grid-cols-2">
                <ChartCard title="Model cost per day" subtitle="USD, at list prices">
                  <ColumnChart label="Model cost per day" data={q.data.daily as unknown as Record<string, unknown>[]} series={[{ key: 'cost_usd', label: 'cost', color: 'var(--viz-series-1)' }]} format={usd} />
                </ChartCard>
                <DraftOutcomes o={q.data.drafts} />
              </div>

              <Card className="p-4">
                <div className="flex items-center justify-between">
                  <h2 className="text-sm font-semibold">Daily table</h2>
                  <button className="text-xs font-medium text-indigo-600" onClick={() => setShowTable((v) => !v)} aria-expanded={showTable}>
                    {showTable ? 'Hide' : 'Show'} table
                  </button>
                </div>
                {showTable && (
                  <div className="mt-3 overflow-x-auto">
                    <table className="min-w-full text-sm tabular-nums">
                      <thead className="text-left text-xs text-slate-500">
                        <tr>
                          {['Day', 'Calls', 'Failed', 'Input tokens', 'Output tokens', 'Cost', 'p50', 'p95'].map((h) => (
                            <th key={h} className="px-2 py-1 font-medium">
                              {h}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {q.data.daily.map((d) => (
                          <tr key={d.day}>
                            <td className="px-2 py-1">{shortDate(d.day)}</td>
                            <td className="px-2 py-1">{d.calls}</td>
                            <td className="px-2 py-1">{d.errors}</td>
                            <td className="px-2 py-1">{d.input_tokens.toLocaleString()}</td>
                            <td className="px-2 py-1">{d.output_tokens.toLocaleString()}</td>
                            <td className="px-2 py-1">{usd(d.cost_usd)}</td>
                            <td className="px-2 py-1">{ms(d.latency_p50_ms)}</td>
                            <td className="px-2 py-1">{ms(d.latency_p95_ms)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Card>

              <div className="grid gap-4 lg:grid-cols-2">
                <Card className="p-4">
                  <h2 className="text-sm font-semibold">By model</h2>
                  <ul className="mt-2 divide-y divide-slate-100 text-sm">
                    {q.data.by_model.map((m) => (
                      <li key={m.model} className="flex justify-between py-1.5 tabular-nums">
                        <span>{m.model}</span>
                        <span className="text-slate-600">
                          {m.calls} calls · {usd(m.cost_usd)}
                        </span>
                      </li>
                    ))}
                  </ul>
                </Card>
                <Card className="p-4">
                  <h2 className="text-sm font-semibold">Recent failures</h2>
                  {q.data.recent_failures.length === 0 ? (
                    <p className="mt-2 text-sm text-slate-500">None in this range.</p>
                  ) : (
                    <ul className="mt-2 space-y-1.5 text-xs">
                      {q.data.recent_failures.map((f, i) => (
                        <li key={i} className="flex gap-2">
                          <span aria-hidden="true" className="text-[var(--viz-critical)]">
                            ✕
                          </span>
                          <span className="min-w-0">
                            <span className="font-medium">{f.status}</span> · {f.error} <span className="text-slate-400">· {timeAgo(f.created_at)}</span>
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </Card>
              </div>
            </>
          )}
        </div>
      )}
    </>
  )
}

function DraftOutcomes({ o }: { o: Overview['drafts'] }) {
  const rows = [
    { label: 'Answered with citations', value: (o.by_status.ready ?? 0) + (o.by_status.published ?? 0) },
    { label: 'Insufficient evidence', value: o.by_status.insufficient_evidence ?? 0 },
    { label: 'Failed (provider)', value: o.by_status.failed ?? 0 },
    { label: 'Discarded', value: o.by_status.discarded ?? 0 },
  ]
  const max = Math.max(1, ...rows.map((r) => r.value))
  return (
    <Card className="p-4">
      <h2 className="text-sm font-semibold">Draft outcomes</h2>
      <p className="text-xs text-[var(--viz-muted)]">{o.total} drafts</p>
      <ul className="mt-3 space-y-2" aria-label="Draft outcomes">
        {rows.map((r) => (
          <li key={r.label} className="grid grid-cols-[9.5rem_1fr] items-center gap-2 text-xs">
            <span className="text-[var(--viz-ink-2)]">{r.label}</span>
            <span className="flex items-center gap-2">
              <span className="h-3 rounded-r" style={{ width: `${(r.value / max) * 85}%`, minWidth: r.value ? 3 : 0, background: 'var(--viz-series-1)' }} />
              <span className="font-semibold text-[var(--viz-ink)] tabular-nums">{r.value}</span>
            </span>
          </li>
        ))}
      </ul>
      <dl className="mt-4 grid grid-cols-2 gap-2 text-xs">
        <div>
          <dt className="text-[var(--viz-muted)]">Refused before any model call</dt>
          <dd className="font-semibold">{o.evidence_gate_refusals}</dd>
        </div>
        <div>
          <dt className="text-[var(--viz-muted)]">Published without edits</dt>
          <dd className="font-semibold">
            {o.published_unedited} of {o.published}
          </dd>
        </div>
        <div>
          <dt className="text-[var(--viz-muted)]">Drafts with a removed citation</dt>
          <dd className="font-semibold">{o.drafts_with_removed_citations}</dd>
        </div>
        <div>
          <dt className="text-[var(--viz-muted)]">Citations per answer · retrieval p95</dt>
          <dd className="font-semibold">
            {o.avg_citations_per_answer ?? '—'} · {ms(o.retrieval_p95_ms)}
          </dd>
        </div>
      </dl>
    </Card>
  )
}

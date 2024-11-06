import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { api } from '../api/client'
import type { InboxView, TicketPage } from '../api/types'
import { timeAgo } from '../components/format'
import { PriorityBadge, StatusBadge } from '../components/TicketBadges'
import { Button, Card, EmptyState, ErrorState, Input, Loading, PageHeader, cx } from '../components/ui'

const VIEWS: { id: InboxView; label: string; countKey?: string }[] = [
  { id: 'active', label: 'All active', countKey: 'active' },
  { id: 'mine', label: 'Mine', countKey: 'mine' },
  { id: 'unassigned', label: 'Unassigned', countKey: 'unassigned' },
  { id: 'pending', label: 'Pending', countKey: 'pending' },
  { id: 'escalated', label: 'Escalated', countKey: 'escalated' },
  { id: 'resolved', label: 'Resolved' },
]

export function InboxPage() {
  const [params, setParams] = useSearchParams()
  const view = (params.get('view') as InboxView) ?? 'active'
  const page = Number(params.get('page') ?? 1)
  const q = params.get('q') ?? ''
  const [search, setSearch] = useState(q)

  const counts = useQuery({ queryKey: ['tickets', 'counts'], queryFn: () => api<Record<string, number>>('/tickets/counts'), refetchInterval: 30_000 })
  const tickets = useQuery({
    queryKey: ['tickets', 'list', view, page, q],
    queryFn: () => api<TicketPage>(`/tickets?${new URLSearchParams({ view, page: String(page), q })}`),
    placeholderData: keepPreviousData,
    refetchInterval: 30_000,
  })
  const set = (next: Record<string, string>) => setParams({ view, q, ...next }, { replace: true })
  const pages = tickets.data ? Math.max(1, Math.ceil(tickets.data.total / tickets.data.page_size)) : 1

  return (
    <>
      <PageHeader title="Inbox" description="Customer tickets, most urgent first." />
      <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <nav className="-mx-1 flex gap-1 overflow-x-auto pb-1" aria-label="Ticket views">
          {VIEWS.map((v) => (
            <button
              key={v.id}
              onClick={() => set({ view: v.id, page: '1' })}
              aria-current={view === v.id ? 'page' : undefined}
              className={cx(
                'flex shrink-0 items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium',
                view === v.id ? 'bg-white text-slate-900 shadow-xs ring-1 ring-slate-200' : 'text-slate-600 hover:text-slate-900',
              )}
            >
              {v.label}
              {v.countKey && counts.data && <span className="rounded-full bg-slate-100 px-1.5 text-xs text-slate-600">{counts.data[v.countKey]}</span>}
            </button>
          ))}
        </nav>
        <form
          onSubmit={(e) => {
            e.preventDefault()
            set({ q: search, page: '1' })
          }}
          className="md:w-72"
        >
          <Input type="search" placeholder="Search subject or customer…" aria-label="Search tickets" value={search} onChange={(e) => setSearch(e.target.value)} />
        </form>
      </div>

      {tickets.isPending ? (
        <Loading />
      ) : tickets.isError ? (
        <ErrorState error={tickets.error} onRetry={() => void tickets.refetch()} />
      ) : tickets.data.items.length === 0 ? (
        <EmptyState title={q ? 'No tickets match your search' : 'Nothing here'}>{q ? 'Try a different search term.' : 'This view is empty. Nice work.'}</EmptyState>
      ) : (
        <Card className={cx(tickets.isPlaceholderData && 'opacity-60')}>
          <ul className="divide-y divide-slate-100">
            {tickets.data.items.map((t) => (
              <li key={t.id}>
                <Link to={`/tickets/${t.id}`} className="block px-4 py-3 hover:bg-slate-50">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="flex flex-wrap items-center gap-2">
                        <span className="truncate font-medium text-slate-900">{t.subject}</span>
                        <PriorityBadge priority={t.priority} />
                      </p>
                      <p className="mt-0.5 truncate text-sm text-slate-500">
                        {t.customer_name} — {t.preview}
                      </p>
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-1">
                      <StatusBadge status={t.status} />
                      <span className="text-xs text-slate-400">{timeAgo(t.updated_at)}</span>
                    </div>
                  </div>
                  <p className="mt-1 text-xs text-slate-400">
                    #{t.id} · {t.assignee ? `Assigned to ${t.assignee.name}` : 'Unassigned'}
                  </p>
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      )}
      {pages > 1 && (
        <div className="mt-4 flex items-center justify-between text-sm text-slate-600">
          <span>
            Page {page} of {pages} · {tickets.data?.total} tickets
          </span>
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => set({ page: String(page - 1) })}>
              Previous
            </Button>
            <Button variant="secondary" size="sm" disabled={page >= pages} onClick={() => set({ page: String(page + 1) })}>
              Next
            </Button>
          </div>
        </div>
      )}
    </>
  )
}

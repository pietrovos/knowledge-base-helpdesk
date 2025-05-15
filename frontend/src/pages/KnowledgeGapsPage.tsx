import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { api } from '../api/client'
import type { KnowledgeGap } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { timeAgo } from '../components/format'
import { Badge, Button, Card, EmptyState, ErrorState, InlineError, Input, Loading, PageHeader, cx } from '../components/ui'

type GapStatus = KnowledgeGap['status']
const TABS: GapStatus[] = ['open', 'resolved', 'dismissed']

export function KnowledgeGapsPage() {
  const [params, setParams] = useSearchParams()
  const status = (params.get('status') as GapStatus) ?? 'open'
  const gaps = useQuery({ queryKey: ['knowledge-gaps', status], queryFn: () => api<KnowledgeGap[]>(`/knowledge-gaps?status=${status}`) })

  return (
    <>
      <PageHeader title="Knowledge gaps" description="Questions customers asked that the knowledge base couldn't answer. Close them by publishing the missing document." />
      <nav className="mb-4 flex gap-1" aria-label="Gap status">
        {TABS.map((s) => (
          <button
            key={s}
            onClick={() => setParams({ status: s }, { replace: true })}
            aria-current={status === s ? 'page' : undefined}
            className={cx('rounded-md px-3 py-1.5 text-sm font-medium capitalize', status === s ? 'bg-white shadow-xs ring-1 ring-slate-200' : 'text-slate-600 hover:text-slate-900')}
          >
            {s}
          </button>
        ))}
      </nav>
      {gaps.isPending ? (
        <Loading />
      ) : gaps.isError ? (
        <ErrorState error={gaps.error} onRetry={() => void gaps.refetch()} />
      ) : gaps.data.length === 0 ? (
        <EmptyState title={`No ${status} gaps`}>{status === 'open' ? 'When a draft finds insufficient evidence, agents can file the question here.' : null}</EmptyState>
      ) : (
        <ul className="space-y-3" aria-label="Knowledge gaps">
          {gaps.data.map((g) => (
            <GapCard key={g.id} gap={g} />
          ))}
        </ul>
      )}
    </>
  )
}

function GapCard({ gap }: { gap: KnowledgeGap }) {
  const { user } = useAuth()
  const qc = useQueryClient()
  const [note, setNote] = useState('')
  const [resolving, setResolving] = useState(false)
  const update = useMutation({
    mutationFn: (patch: Record<string, unknown>) => api<KnowledgeGap>(`/knowledge-gaps/${gap.id}`, { method: 'PATCH', json: patch }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['knowledge-gaps'] }),
  })
  return (
    <li>
      <Card className="p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <p className="font-medium text-slate-900">“{gap.question}”</p>
            {gap.missing_information && <p className="mt-1 text-sm text-slate-600">{gap.missing_information}</p>}
            <p className="mt-2 text-xs text-slate-500">
              #{gap.id} · reported by {gap.created_by?.name ?? 'someone'} {timeAgo(gap.created_at)}
              {gap.ticket_id && (
                <>
                  {' · '}
                  <Link to={`/tickets/${gap.ticket_id}`} className="text-indigo-600 hover:underline">
                    ticket #{gap.ticket_id}
                  </Link>
                </>
              )}
            </p>
            {gap.status !== 'open' && (
              <p className="mt-2 text-xs text-slate-600">
                <Badge tone={gap.status === 'resolved' ? 'green' : 'slate'}>{gap.status}</Badge> by {gap.resolved_by?.name} {gap.resolved_at && timeAgo(gap.resolved_at)}
                {gap.resolution_note && ` — ${gap.resolution_note}`}
              </p>
            )}
          </div>
          {user?.role === 'admin' && (
            <div className="flex shrink-0 gap-2">
              {gap.status === 'open' ? (
                <>
                  <Button size="sm" variant="secondary" onClick={() => setResolving((v) => !v)}>
                    Resolve
                  </Button>
                  <Button size="sm" variant="ghost" loading={update.isPending} onClick={() => update.mutate({ status: 'dismissed' })}>
                    Dismiss
                  </Button>
                </>
              ) : (
                <Button size="sm" variant="ghost" onClick={() => update.mutate({ status: 'open' })}>
                  Reopen
                </Button>
              )}
            </div>
          )}
        </div>
        {resolving && (
          <form
            className="mt-3 flex gap-2"
            onSubmit={(e) => {
              e.preventDefault()
              update.mutate({ status: 'resolved', resolution_note: note })
            }}
          >
            <Input aria-label="Resolution note" placeholder="e.g. Published 'Router troubleshooting' in Product Handbook" value={note} onChange={(e) => setNote(e.target.value)} />
            <Button type="submit" size="sm" loading={update.isPending}>
              Mark resolved
            </Button>
          </form>
        )}
        <InlineError error={update.error} />
      </Card>
    </li>
  )
}

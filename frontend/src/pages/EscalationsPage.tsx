import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router'
import { api } from '../api/client'
import type { TicketPage } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { timeAgo } from '../components/format'
import { PriorityBadge } from '../components/TicketBadges'
import { Button, Card, EmptyState, ErrorState, InlineError, Loading, PageHeader } from '../components/ui'

export function EscalationsPage() {
  const { user } = useAuth()
  const qc = useQueryClient()
  const tickets = useQuery({
    queryKey: ['tickets', 'list', 'escalated'],
    queryFn: () => api<TicketPage>('/tickets?view=escalated&page_size=100'),
    refetchInterval: 30_000,
  })
  const update = useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: Record<string, unknown> }) => api(`/tickets/${id}`, { method: 'PATCH', json: patch }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['tickets'] }),
  })

  return (
    <>
      <PageHeader title="Escalations" description="Tickets that need a senior agent, a specialist or a policy decision." />
      <InlineError error={update.error} />
      {tickets.isPending ? (
        <Loading />
      ) : tickets.isError ? (
        <ErrorState error={tickets.error} onRetry={() => void tickets.refetch()} />
      ) : tickets.data.items.length === 0 ? (
        <EmptyState title="No escalated tickets">Escalate a ticket from its detail page when it needs someone else.</EmptyState>
      ) : (
        <div className="space-y-3">
          {tickets.data.items.map((t) => (
            <Card key={t.id} className="p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <Link to={`/tickets/${t.id}`} className="font-medium text-slate-900 hover:text-indigo-700">
                    #{t.id} {t.subject}
                  </Link>{' '}
                  <PriorityBadge priority={t.priority} />
                  <p className="mt-1 text-sm text-red-800">{t.escalation_reason}</p>
                  <p className="mt-1 text-xs text-slate-500">
                    {t.customer_name} · updated {timeAgo(t.updated_at)} · {t.assignee ? `with ${t.assignee.name}` : 'unassigned'}
                  </p>
                </div>
                <div className="flex shrink-0 gap-2">
                  {t.assignee?.id !== user?.id && (
                    <Button size="sm" variant="secondary" onClick={() => update.mutate({ id: t.id, patch: { assignee_id: user!.id } })}>
                      Take it
                    </Button>
                  )}
                  <Button size="sm" variant="secondary" onClick={() => update.mutate({ id: t.id, patch: { status: 'open' } })}>
                    De-escalate
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </>
  )
}

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import { Link, useParams } from 'react-router'
import { api } from '../api/client'
import type { TicketDetail, TicketEvent, TicketMessage, TicketPriority, TicketStatus, UserRef } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { timeAgo } from '../components/format'
import { DraftPanel } from '../components/DraftPanel'
import { PriorityBadge, StatusBadge, cap } from '../components/TicketBadges'
import { Button, Card, ErrorState, InlineError, Label, Loading, Select, Textarea, cx } from '../components/ui'

export function TicketPage() {
  const id = Number(useParams().ticketId)
  const ticket = useQuery({ queryKey: ['tickets', id], queryFn: () => api<TicketDetail>(`/tickets/${id}`) })

  if (ticket.isPending) return <Loading />
  if (ticket.isError) return <ErrorState error={ticket.error} onRetry={() => void ticket.refetch()} />
  const t = ticket.data

  return (
    <>
      <Link to="/tickets" className="text-sm text-slate-500 hover:text-slate-700">
        ← Inbox
      </Link>
      <div className="mt-1 mb-6 flex flex-wrap items-center gap-2">
        <h1 className="text-xl font-semibold text-slate-900">{t.subject}</h1>
        <StatusBadge status={t.status} />
        <PriorityBadge priority={t.priority} />
      </div>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <div className="min-w-0 space-y-6">
          <Conversation ticket={t} />
          <DraftPanel ticketId={t.id} />
          <Composer ticket={t} />
        </div>
        <aside className="space-y-6">
          <Properties ticket={t} />
          <Activity events={t.events} />
        </aside>
      </div>
    </>
  )
}

function Conversation({ ticket }: { ticket: TicketDetail }) {
  return (
    <section aria-label="Conversation" className="space-y-4">
      {ticket.messages.map((m) => (
        <Message key={m.id} message={m} customer={ticket.customer_name} />
      ))}
    </section>
  )
}

function Message({ message: m, customer }: { message: TicketMessage; customer: string }) {
  const isCustomer = m.author_type === 'customer'
  return (
    <Card className={cx('p-4', m.is_internal && 'bg-amber-50 ring-amber-200', !isCustomer && !m.is_internal && 'ring-indigo-200')}>
      <div className="mb-2 flex flex-wrap items-center gap-2 text-sm">
        <span className="font-medium">{isCustomer ? customer : (m.author?.name ?? 'Agent')}</span>
        <span className="text-slate-400">{isCustomer ? 'Customer' : m.is_internal ? 'Internal note' : 'Reply'}</span>
        {m.draft_id && <span className="text-xs text-indigo-600">from cited draft</span>}
        <span className="ml-auto text-xs text-slate-400">{timeAgo(m.created_at)}</span>
      </div>
      <p className="text-sm whitespace-pre-wrap text-slate-800">{m.body}</p>
    </Card>
  )
}

export function useTicketMutation(ticketId: number) {
  const qc = useQueryClient()
  return () => {
    void qc.invalidateQueries({ queryKey: ['tickets'] })
    void qc.invalidateQueries({ queryKey: ['tickets', ticketId] })
  }
}

function Composer({ ticket, initial = '' }: { ticket: TicketDetail; initial?: string }) {
  const refresh = useTicketMutation(ticket.id)
  const [body, setBody] = useState(initial)
  const [internal, setInternal] = useState(false)
  const send = useMutation({
    mutationFn: (status?: TicketStatus) => api(`/tickets/${ticket.id}/messages`, { method: 'POST', json: { body, is_internal: internal, ...(status ? { status } : {}) } }),
    onSuccess: () => {
      setBody('')
      refresh()
    },
  })
  return (
    <Card className="p-4">
      <div className="mb-2 flex gap-4 text-sm">
        <label className="flex items-center gap-1.5">
          <input type="radio" checked={!internal} onChange={() => setInternal(false)} /> Reply to customer
        </label>
        <label className="flex items-center gap-1.5">
          <input type="radio" checked={internal} onChange={() => setInternal(true)} /> Internal note
        </label>
      </div>
      <Textarea rows={5} aria-label="Message" placeholder={internal ? 'Only visible to your team…' : 'Write a reply…'} value={body} onChange={(e) => setBody(e.target.value)} />
      <div className="mt-3 flex flex-wrap justify-end gap-2">
        {!internal && (
          <Button variant="secondary" disabled={!body.trim()} loading={send.isPending && send.variables === 'pending'} onClick={() => send.mutate('pending')}>
            Send & mark pending
          </Button>
        )}
        <Button disabled={!body.trim()} loading={send.isPending && send.variables === undefined} onClick={() => send.mutate(undefined)}>
          {internal ? 'Add note' : 'Send reply'}
        </Button>
      </div>
      <InlineError error={send.error} />
    </Card>
  )
}

function Properties({ ticket: t }: { ticket: TicketDetail }) {
  const { user } = useAuth()
  const refresh = useTicketMutation(t.id)
  const directory = useQuery({ queryKey: ['users', 'directory'], queryFn: () => api<UserRef[]>('/users/directory') })
  const [escalating, setEscalating] = useState(false)
  const [reason, setReason] = useState('')
  const update = useMutation({
    mutationFn: (patch: Record<string, unknown>) => api<TicketDetail>(`/tickets/${t.id}`, { method: 'PATCH', json: patch }),
    onSuccess: () => {
      setEscalating(false)
      setReason('')
      refresh()
    },
  })

  return (
    <Card className="space-y-4 p-4">
      <div>
        <p className="text-sm font-medium">{t.customer_name}</p>
        <p className="text-xs text-slate-500">{t.customer_email}</p>
      </div>
      <div>
        <Label htmlFor="status">Status</Label>
        <Select
          id="status"
          value={t.status}
          onChange={(e) => {
            const status = e.target.value as TicketStatus
            if (status === 'escalated') setEscalating(true)
            else update.mutate({ status })
          }}
        >
          {(['open', 'pending', 'escalated', 'resolved', 'closed'] as const).map((s) => (
            <option key={s} value={s}>
              {cap(s)}
            </option>
          ))}
        </Select>
      </div>
      {(escalating || t.status === 'escalated') && (
        <div className="rounded-md bg-red-50 p-3 ring-1 ring-red-200">
          {t.status === 'escalated' && !escalating ? (
            <p className="text-sm text-red-800">
              <span className="font-medium">Escalated:</span> {t.escalation_reason}
            </p>
          ) : (
            <EscalateForm reason={reason} setReason={setReason} pending={update.isPending} onCancel={() => setEscalating(false)} onSubmit={() => update.mutate({ status: 'escalated', escalation_reason: reason })} />
          )}
        </div>
      )}
      <div>
        <Label htmlFor="priority">Priority</Label>
        <Select id="priority" value={t.priority} onChange={(e) => update.mutate({ priority: e.target.value as TicketPriority })}>
          {(['low', 'normal', 'high', 'urgent'] as const).map((p) => (
            <option key={p} value={p}>
              {cap(p)}
            </option>
          ))}
        </Select>
      </div>
      <div>
        <Label htmlFor="assignee">Assignee</Label>
        <Select id="assignee" value={t.assignee?.id ?? ''} onChange={(e) => update.mutate(e.target.value ? { assignee_id: Number(e.target.value) } : { unassign: true })}>
          <option value="">Unassigned</option>
          {(directory.data ?? []).map((u) => (
            <option key={u.id} value={u.id}>
              {u.name}
              {u.id === user?.id ? ' (me)' : ''}
            </option>
          ))}
        </Select>
        {t.assignee?.id !== user?.id && user && (
          <button className="mt-1 text-xs font-medium text-indigo-600 hover:text-indigo-500" onClick={() => update.mutate({ assignee_id: user.id })}>
            Assign to me
          </button>
        )}
      </div>
      <InlineError error={update.error} />
    </Card>
  )
}

function EscalateForm(props: { reason: string; setReason: (s: string) => void; pending: boolean; onCancel: () => void; onSubmit: () => void }) {
  return (
    <div className="space-y-2">
      <Label htmlFor="escalation-reason">Why does this need escalation?</Label>
      <Textarea id="escalation-reason" rows={3} value={props.reason} onChange={(e) => props.setReason(e.target.value)} />
      <div className="flex justify-end gap-2">
        <Button size="sm" variant="ghost" onClick={props.onCancel}>
          Cancel
        </Button>
        <Button size="sm" variant="danger" disabled={!props.reason.trim()} loading={props.pending} onClick={props.onSubmit}>
          Escalate
        </Button>
      </div>
    </div>
  )
}

function describe(e: TicketEvent): ReactNode {
  const d = e.data as Record<string, string>
  switch (e.kind) {
    case 'created':
      return e.actor ? 'created the ticket' : `received the ticket by ${String(d.channel ?? 'email')}`
    case 'status_changed':
      return (
        <>
          changed status to <b>{d.to}</b>
          {d.reason ? ` — ${d.reason}` : ''}
        </>
      )
    case 'priority_changed':
      return (
        <>
          set priority to <b>{d.to}</b>
        </>
      )
    case 'assigned':
      return (
        <>
          assigned to <b>{d.assignee_name}</b>
        </>
      )
    case 'unassigned':
      return 'unassigned the ticket'
    default:
      return e.kind.replaceAll('_', ' ')
  }
}

function Activity({ events }: { events: TicketEvent[] }) {
  return (
    <Card className="p-4">
      <h2 className="mb-3 text-sm font-semibold">Activity</h2>
      {events.length === 0 && <p className="text-xs text-slate-500">No activity yet.</p>}
      <ol className="space-y-2 text-xs text-slate-600">
        {[...events].reverse().map((e) => (
          <li key={e.id}>
            <span className="font-medium text-slate-800">{e.actor?.name ?? 'System'}</span> {describe(e)}
            <span className="text-slate-400"> · {timeAgo(e.created_at)}</span>
          </li>
        ))}
      </ol>
    </Card>
  )
}

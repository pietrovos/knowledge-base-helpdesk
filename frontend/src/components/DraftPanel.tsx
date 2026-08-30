import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router'
import { api } from '../api/client'
import type { Draft, KnowledgeGap } from '../api/types'
import { parseCitations } from './citations'
import { EvidenceDrawer } from './EvidenceDrawer'
import { sectionLabel } from './format'
import { useSystemStatus } from './useSystemStatus'
import { Badge, Button, Card, InlineError, Input, Spinner, cx } from './ui'

const terminal = (d: Draft) => d.status !== 'pending'

export function useDrafts(ticketId: number) {
  return useQuery({
    queryKey: ['tickets', ticketId, 'drafts'],
    queryFn: () => api<Draft[]>(`/tickets/${ticketId}/drafts`),
    refetchInterval: (q) => (q.state.data?.some((d) => !terminal(d)) ? 800 : false),
  })
}

export function DraftPanel({ ticketId, onUseDraft }: { ticketId: number; onUseDraft?: (draft: Draft) => void }) {
  const qc = useQueryClient()
  const drafts = useDrafts(ticketId)
  const [question, setQuestion] = useState('')
  const [askOpen, setAskOpen] = useState(false)
  const request = useMutation({
    mutationFn: (q?: string) => api<Draft>(`/tickets/${ticketId}/drafts`, { method: 'POST', json: q ? { question: q } : {} }),
    onSuccess: () => {
      setQuestion('')
      setAskOpen(false)
      void qc.invalidateQueries({ queryKey: ['tickets', ticketId, 'drafts'] })
    },
  })
  const latest = drafts.data?.find((d) => d.status !== 'discarded')
  const busy = latest?.status === 'pending' || request.isPending
  const system = useSystemStatus()
  const unavailable = system.data ? !system.data.drafting_available : false

  // Clearing a question discards every unsent question draft on this ticket, so the panel goes
  // back to the ticket's own draft rather than surfacing an older question.
  const clear = useMutation({
    mutationFn: () =>
      Promise.all(
        (drafts.data ?? [])
          .filter((d) => d.custom_question && d.status !== 'discarded' && d.status !== 'published')
          .map((d) => api(`/drafts/${d.id}/discard`, { method: 'POST' })),
      ),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['tickets', ticketId, 'drafts'] }),
  })
  const openAsk = () => {
    setQuestion('')
    setAskOpen(true)
  }

  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="font-semibold">Cited draft</h2>
          <p className="text-xs text-slate-500">Grounded only in knowledge you can access. Every claim links to its source.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" onClick={() => (askOpen ? setAskOpen(false) : openAsk())} disabled={busy || unavailable}>
            Ask a question
          </Button>
          <Button size="sm" onClick={() => request.mutate(undefined)} loading={busy && !latest?.custom_question} disabled={busy || unavailable}>
            {latest && !latest.custom_question ? 'Regenerate' : 'Draft reply'}
          </Button>
        </div>
      </div>
      {askOpen && (
        <form
          className="mt-3 flex gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            if (question.trim()) request.mutate(question.trim())
          }}
          onKeyDown={(e) => e.key === 'Escape' && setAskOpen(false)}
        >
          <Input
            autoFocus
            aria-label="Question for the knowledge base"
            placeholder="e.g. Can international orders be refunded?"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
          />
          <Button type="button" variant="ghost" size="sm" onClick={() => setAskOpen(false)}>
            Cancel
          </Button>
          <Button type="submit" size="sm" disabled={!question.trim() || busy}>
            Ask
          </Button>
        </form>
      )}
      {unavailable && (
        <p className="mt-3 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-900 ring-1 ring-amber-200" data-testid="drafting-paused">
          AI drafting is paused: {system.data?.degraded_reasons[0]} You can still reply manually below.
        </p>
      )}
      {latest?.custom_question && !askOpen && (
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-md bg-indigo-50 px-3 py-2 ring-1 ring-indigo-100" data-testid="question-bar">
          <p className="min-w-0 text-sm text-slate-700">
            <span className="text-slate-500">Answering your question:</span> “{latest.question}”
          </p>
          <div className="flex shrink-0 gap-2">
            <Button size="sm" variant="secondary" onClick={openAsk} disabled={busy || unavailable}>
              Ask another
            </Button>
            {latest.status !== 'published' && (
              <Button size="sm" variant="ghost" onClick={() => clear.mutate()} loading={clear.isPending} disabled={latest.status === 'pending'}>
                Clear question
              </Button>
            )}
          </div>
        </div>
      )}
      <InlineError error={request.error ?? clear.error} />
      {latest && !(unavailable && latest.status === 'failed') && <DraftView draft={latest} onUseDraft={onUseDraft} />}
    </Card>
  )
}

function DraftView({ draft, onUseDraft }: { draft: Draft; onUseDraft?: (d: Draft) => void }) {
  const [open, setOpen] = useState<{ chunkId: number; label: number } | null>(null)
  const cited = draft.sources.filter((s) => s.cited)
  const labelOf = new Map(cited.map((s, i) => [s.chunk_id, i + 1]))

  if (draft.status === 'pending') {
    return (
      <div className="mt-4 flex items-center gap-2 rounded-md bg-slate-50 p-4 text-sm text-slate-600" role="status">
        <Spinner className="size-4" /> Searching your knowledge and drafting a reply…
      </div>
    )
  }

  if (draft.status === 'failed') {
    return (
      <div className="mt-4 rounded-md bg-amber-50 p-4 text-sm text-amber-900 ring-1 ring-amber-200" role="alert" data-testid="draft-failed">
        <p className="font-medium">Drafting is unavailable right now</p>
        <p className="mt-1">{draft.error}</p>
        <p className="mt-1 text-amber-800">The ticket is fully usable: reply manually below, or try again in a moment.</p>
      </div>
    )
  }

  return (
    <div className="mt-4 space-y-4">
      {draft.status === 'insufficient_evidence' ? (
        <InsufficientEvidence draft={draft} />
      ) : (
        <>
          {draft.invalid_citation_ids.length > 0 && (
            <p className="rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-800 ring-1 ring-amber-200" role="note">
              {draft.invalid_citation_ids.length} citation{draft.invalid_citation_ids.length > 1 ? 's were' : ' was'} removed because
              {draft.invalid_citation_ids.length > 1 ? ' they' : ' it'} referenced passages that weren't retrieved. Review the text around it before sending.
            </p>
          )}
          <div className="rounded-md bg-indigo-50/40 p-4 text-sm leading-relaxed whitespace-pre-wrap ring-1 ring-indigo-100" data-testid="draft-reply">
            {parseCitations(draft.reply).map((seg, i) =>
              seg.kind === 'text' ? (
                <span key={i}>{seg.text}</span>
              ) : (
                <button
                  key={i}
                  onClick={() => setOpen({ chunkId: seg.chunkId, label: labelOf.get(seg.chunkId) ?? 0 })}
                  className="mx-0.5 inline-flex -translate-y-0.5 items-center rounded bg-indigo-600 px-1.5 text-[11px] font-semibold text-white hover:bg-indigo-500"
                  aria-label={`Citation ${labelOf.get(seg.chunkId)}`}
                >
                  {labelOf.get(seg.chunkId)}
                </button>
              ),
            )}
          </div>
          {draft.status === 'published' ? (
            <Badge tone="green">Published</Badge>
          ) : (
            onUseDraft && (
              <div className="flex justify-end">
                <Button size="sm" onClick={() => onUseDraft(draft)}>
                  Edit & send
                </Button>
              </div>
            )
          )}
        </>
      )}
      <Sources draft={draft} labelOf={labelOf} onOpen={(chunkId, label) => setOpen({ chunkId, label })} />
      <p className="text-[11px] text-slate-400">
        {draft.decided_by === 'evidence_gate' ? 'No model call: retrieval found nothing relevant' : `${draft.model ?? ''}`}
        {draft.retrieval_ms !== null && ` · retrieval ${draft.retrieval_ms} ms`}
        {draft.generation_ms !== null && ` · generation ${(draft.generation_ms / 1000).toFixed(1)} s`}
        {draft.embedding_model && ` · ${draft.embedding_model}`}
      </p>
      {open && <EvidenceDrawer draftId={draft.id} chunkId={open.chunkId} label={open.label} onClose={() => setOpen(null)} />}
    </div>
  )
}

function Sources({ draft, labelOf, onOpen }: { draft: Draft; labelOf: Map<number, number>; onOpen: (chunkId: number, label: number) => void }) {
  if (draft.sources.length === 0) return null
  return (
    <details open={draft.status === 'ready'}>
      <summary className="cursor-pointer text-xs font-medium text-slate-600">
        {draft.sources.length} passages retrieved · {labelOf.size} cited
      </summary>
      <ul className="mt-2 space-y-1.5" aria-label="Retrieved passages">
        {draft.sources.map((s) => {
          const label = labelOf.get(s.chunk_id)
          return (
            <li key={s.chunk_id}>
              <button
                onClick={() => onOpen(s.chunk_id, label ?? 0)}
                disabled={!s.accessible}
                className={cx('flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left text-xs hover:bg-slate-50 disabled:cursor-not-allowed', !s.cited && 'opacity-70')}
              >
                <span className={cx('mt-0.5 inline-flex min-w-5 justify-center rounded px-1 font-semibold', label ? 'bg-indigo-600 text-white' : 'bg-slate-200 text-slate-600')}>{label ?? '–'}</span>
                <span className="min-w-0">
                  <span className="font-medium text-slate-800">{s.document_title}</span>
                  {sectionLabel(s.document_title, s.heading) && <span className="text-slate-500"> › {sectionLabel(s.document_title, s.heading)}</span>}
                  {!s.live && <span className="text-amber-700"> · retired</span>}
                  <span className="block truncate text-slate-500">{s.accessible ? s.text : 'Restricted: you no longer have access to this collection'}</span>
                </span>
              </button>
            </li>
          )
        })}
      </ul>
    </details>
  )
}

function InsufficientEvidence({ draft }: { draft: Draft }) {
  const qc = useQueryClient()
  const createGap = useMutation({
    mutationFn: () => api<KnowledgeGap>('/knowledge-gaps', { method: 'POST', json: { draft_id: draft.id } }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['tickets', draft.ticket_id] })
      void qc.invalidateQueries({ queryKey: ['knowledge-gaps'] })
    },
  })
  const reason = {
    evidence_gate: 'Nothing in the knowledge you can access is close enough to this question.',
    model: 'The retrieved passages don’t answer this question.',
    validator: 'The generated answer couldn’t be tied to any retrieved passage, so it was withheld.',
  }[draft.decided_by ?? 'model']
  return (
    <div className="rounded-md bg-slate-50 p-4 text-sm ring-1 ring-slate-200" data-testid="insufficient-evidence">
      <p className="font-medium text-slate-900">Insufficient evidence: no draft was written</p>
      <p className="mt-1 text-slate-600">{reason}</p>
      {draft.missing_information && <p className="mt-2 text-slate-600">Missing: {draft.missing_information}</p>}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {draft.knowledge_gap_id ? (
          <span className="text-sm text-emerald-700">
            Knowledge-gap task #{draft.knowledge_gap_id} created ·{' '}
            <Link to="/knowledge-gaps" className="font-medium underline">
              view queue
            </Link>
          </span>
        ) : (
          <Button size="sm" variant="secondary" loading={createGap.isPending} onClick={() => createGap.mutate()}>
            Create knowledge-gap task
          </Button>
        )}
      </div>
      <EscalateInline draft={draft} />
      <InlineError error={createGap.error} />
    </div>
  )
}

function EscalateInline({ draft }: { draft: Draft }) {
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState(`Knowledge base can't answer: ${draft.question.slice(0, 160)}`)
  const escalate = useMutation({
    mutationFn: () => api(`/tickets/${draft.ticket_id}`, { method: 'PATCH', json: { status: 'escalated', escalation_reason: reason } }),
    onSuccess: () => {
      setOpen(false)
      void qc.invalidateQueries({ queryKey: ['tickets'] })
    },
  })
  if (!open)
    return (
      <button className="mt-3 text-xs font-medium text-red-700 hover:underline" onClick={() => setOpen(true)}>
        Escalate this ticket instead
      </button>
    )
  return (
    <div className="mt-3 space-y-2">
      <Input aria-label="Escalation reason" value={reason} onChange={(e) => setReason(e.target.value)} />
      <div className="flex justify-end gap-2">
        <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>
          Cancel
        </Button>
        <Button size="sm" variant="danger" disabled={!reason.trim()} loading={escalate.isPending} onClick={() => escalate.mutate()}>
          Escalate
        </Button>
      </div>
      <InlineError error={escalate.error} />
    </div>
  )
}

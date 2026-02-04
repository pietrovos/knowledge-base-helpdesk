import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../api/client'
import type { Draft } from '../api/types'
import { stripCitations } from './citations'
import { sectionLabel } from './format'
import { Badge, Button, Card, InlineError, Textarea } from './ui'

/** Agent edits the cited draft, then sends it. Citation markers are internal: the customer gets
 *  plain text, and the draft keeps its sources as the audit trail. */
export function PublishEditor({ draft, onClose }: { draft: Draft; onClose: () => void }) {
  const qc = useQueryClient()
  const [text, setText] = useState(() => stripCitations(draft.reply))
  const publish = useMutation({
    mutationFn: (ticket_status?: 'pending' | 'resolved') =>
      api<Draft>(`/drafts/${draft.id}/publish`, { method: 'POST', json: { text, ...(ticket_status ? { ticket_status } : {}) } }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['tickets'] })
      onClose()
    },
  })
  const cited = draft.sources.filter((s) => s.cited)
  const edited = text.trim() !== stripCitations(draft.reply)

  return (
    <Card className="p-4 ring-indigo-300" >
      <div className="mb-2 flex items-center justify-between">
        <h2 className="font-semibold">Review and send</h2>
        {edited && <Badge tone="amber">Edited</Badge>}
      </div>
      <Textarea rows={10} aria-label="Reply to send" value={text} onChange={(e) => setText(e.target.value)} />
      <div className="mt-2 text-xs text-slate-500">
        Based on {cited.length} cited passage{cited.length === 1 ? '' : 's'}:{' '}
        {cited.map((s) => `${s.document_title}${sectionLabel(s.document_title, s.heading) ? ` › ${sectionLabel(s.document_title, s.heading)}` : ''}`).join(' · ')}
        {edited && ' — check that your edits are still supported by these sources.'}
      </div>
      <div className="mt-3 flex flex-wrap justify-end gap-2">
        <Button variant="ghost" onClick={onClose}>
          Cancel
        </Button>
        <Button variant="secondary" disabled={!text.trim()} loading={publish.isPending && publish.variables === 'resolved'} onClick={() => publish.mutate('resolved')}>
          Send & resolve
        </Button>
        <Button variant="secondary" disabled={!text.trim()} loading={publish.isPending && publish.variables === 'pending'} onClick={() => publish.mutate('pending')}>
          Send & mark pending
        </Button>
        <Button disabled={!text.trim()} loading={publish.isPending && publish.variables === undefined} onClick={() => publish.mutate(undefined)}>
          Send
        </Button>
      </div>
      <InlineError error={publish.error} />
    </Card>
  )
}

import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'
import { Link } from 'react-router'
import { ApiError, api } from '../api/client'
import type { Evidence } from '../api/types'
import { Badge, ErrorState, Loading } from './ui'

export function EvidenceDrawer({ draftId, chunkId, label, onClose }: { draftId: number; chunkId: number; label: number; onClose: () => void }) {
  const evidence = useQuery({
    queryKey: ['evidence', draftId, chunkId],
    queryFn: () => api<Evidence>(`/drafts/${draftId}/evidence/${chunkId}`),
    retry: false,
  })
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const forbidden = evidence.error instanceof ApiError && evidence.error.status === 403
  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" aria-label={`Evidence for citation ${label}`}>
      <div className="absolute inset-0 bg-slate-900/40" onClick={onClose} />
      <div className="relative flex h-full w-full max-w-xl flex-col bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <h2 className="font-semibold">Evidence [{label}]</h2>
          <button onClick={onClose} className="rounded-md p-1 text-slate-500 hover:bg-slate-100" aria-label="Close evidence">
            ✕
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {evidence.isPending ? (
            <Loading />
          ) : forbidden ? (
            <div role="alert" className="rounded-md bg-amber-50 p-4 text-sm text-amber-800 ring-1 ring-amber-200">
              You no longer have access to this source. Its collection was restricted after the draft was generated.
            </div>
          ) : evidence.isError ? (
            <ErrorState error={evidence.error} />
          ) : (
            <>
              <div className="mb-4">
                <Link to={`/documents/${evidence.data.source.document_id}`} className="font-medium text-indigo-700 hover:underline">
                  {evidence.data.source.document_title}
                </Link>
                <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                  <Badge>{evidence.data.collection_name}</Badge>
                  <span>v{evidence.data.source.version}</span>
                  {evidence.data.source.heading && <span>› {evidence.data.source.heading}</span>}
                  {evidence.data.source.live ? <Badge tone="green">Current</Badge> : <Badge tone="amber">Retired since drafting</Badge>}
                  {evidence.data.source.similarity !== null && <span>similarity {evidence.data.source.similarity.toFixed(2)}</span>}
                </div>
              </div>
              {!evidence.data.source.live && (
                <p className="mb-3 text-xs text-amber-700">This passage has been replaced by a newer version or deleted. Below is exactly what the draft was based on.</p>
              )}
              <div className="space-y-3 text-sm leading-relaxed">
                {evidence.data.context_before && <p className="whitespace-pre-wrap text-slate-400">{evidence.data.context_before}</p>}
                <blockquote data-testid="evidence-passage" className="rounded-md border-l-4 border-indigo-500 bg-indigo-50 px-4 py-3 whitespace-pre-wrap text-slate-900">
                  {evidence.data.source.text}
                </blockquote>
                {evidence.data.context_after && <p className="whitespace-pre-wrap text-slate-400">{evidence.data.context_after}</p>}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { api } from '../api/client'
import type { ChunkRow, DocumentDetail, DocVersion } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { bytes, timeAgo } from '../components/format'
import { UploadButton } from '../components/UploadButton'
import { Button, Card, ErrorState, InlineError, Loading, PageHeader } from '../components/ui'
import { isBusy, VersionProgress, VersionStatusBadge } from '../components/VersionStatus'

export function DocumentPage() {
  const id = Number(useParams().documentId)
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'
  const navigate = useNavigate()
  const qc = useQueryClient()
  const doc = useQuery({
    queryKey: ['documents', id],
    queryFn: () => api<DocumentDetail>(`/documents/${id}`),
    refetchInterval: (q) => (q.state.data?.versions.some(isBusy) ? 1000 : false),
  })
  const del = useMutation({
    mutationFn: () => api(`/documents/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['documents'] })
      void qc.invalidateQueries({ queryKey: ['collections'] })
      navigate(`/collections/${doc.data?.collection_id}`)
    },
  })

  if (doc.isPending) return <Loading />
  if (doc.isError) return <ErrorState error={doc.error} onRetry={() => void doc.refetch()} />
  const d = doc.data

  return (
    <>
      <Link to={`/collections/${d.collection_id}`} className="text-sm text-slate-500 hover:text-slate-700">
        ← {d.collection_name}
      </Link>
      <PageHeader
        title={d.title}
        description={`${d.filename} · ${d.current_version ? `v${d.current_version.version} is live` : 'no live version yet'}`}
        actions={
          isAdmin && (
            <>
              <UploadButton endpoint={`/documents/${id}/versions`} label="Upload new version" />
              <Button variant="danger" loading={del.isPending} onClick={() => confirm(`Delete "${d.title}"? It will stop being used for drafts immediately.`) && del.mutate()}>
                Delete
              </Button>
            </>
          )
        }
      />
      <InlineError error={del.error} />
      <h2 className="mb-3 font-semibold">Versions</h2>
      <div className="space-y-3">
        {d.versions.map((v) => (
          <VersionCard key={v.id} documentId={id} version={v} isAdmin={isAdmin} />
        ))}
      </div>
    </>
  )
}

function VersionCard({ documentId, version: v, isAdmin }: { documentId: number; version: DocVersion; isAdmin: boolean }) {
  const qc = useQueryClient()
  const [showChunks, setShowChunks] = useState(false)
  const reprocess = useMutation({
    mutationFn: () => api<DocVersion>(`/documents/${documentId}/versions/${v.id}/reprocess`, { method: 'POST' }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['documents'] }),
  })
  const download = useMutation({
    mutationFn: () => api<{ url: string }>(`/documents/${documentId}/versions/${v.id}/download`),
    onSuccess: ({ url }) => window.location.assign(url),
  })
  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="font-medium">v{v.version}</span>
          <VersionStatusBadge version={v} />
          <span className="text-xs text-slate-500">
            {bytes(v.size_bytes)} · uploaded {timeAgo(v.created_at)}
            {v.chunk_count > 0 && ` · ${v.chunk_count} chunks`}
            {v.attempts > 1 && ` · ${v.attempts} attempts`}
          </span>
        </div>
        <div className="flex gap-2">
          {v.chunk_count > 0 && (
            <Button size="sm" variant="secondary" onClick={() => setShowChunks((s) => !s)}>
              {showChunks ? 'Hide chunks' : 'View chunks'}
            </Button>
          )}
          <Button size="sm" variant="secondary" loading={download.isPending} onClick={() => download.mutate()}>
            Download
          </Button>
          {isAdmin && !isBusy(v) && (
            <Button size="sm" variant="secondary" loading={reprocess.isPending} onClick={() => reprocess.mutate()}>
              {v.status === 'failed' ? 'Retry' : 'Reprocess'}
            </Button>
          )}
        </div>
      </div>
      <VersionProgress version={v} />
      {v.error && <p className={`mt-2 text-sm ${v.status === 'failed' ? 'text-red-600' : 'text-amber-700'}`}>{v.error}</p>}
      {v.status === 'superseded' && <p className="mt-2 text-xs text-slate-500">Retired: a newer version replaced it. Its chunks are no longer retrieved.</p>}
      <InlineError error={reprocess.error ?? download.error} />
      {showChunks && <ChunkList documentId={documentId} versionId={v.id} />}
    </Card>
  )
}

function ChunkList({ documentId, versionId }: { documentId: number; versionId: number }) {
  const chunks = useQuery({
    queryKey: ['documents', documentId, 'chunks', versionId],
    queryFn: () => api<ChunkRow[]>(`/documents/${documentId}/versions/${versionId}/chunks`),
  })
  if (chunks.isPending) return <Loading />
  if (chunks.isError) return <ErrorState error={chunks.error} />
  return (
    <ol className="mt-4 space-y-2">
      {chunks.data.map((c) => (
        <li key={c.id} className="rounded-md bg-slate-50 p-3 text-sm ring-1 ring-slate-200">
          <p className="mb-1 text-xs text-slate-500">
            #{c.id} · {c.heading || 'No heading'} · chars {c.char_start}–{c.char_end}
          </p>
          <p className="whitespace-pre-wrap text-slate-700">{c.text}</p>
        </li>
      ))}
    </ol>
  )
}

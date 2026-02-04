import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router'
import { api } from '../api/client'
import type { SearchResponse } from '../api/types'
import { Badge, Button, Card, EmptyState, ErrorState, Input, Loading } from './ui'
import { sectionLabel } from './format'

export function KnowledgeSearch() {
  const [input, setInput] = useState('')
  const [q, setQ] = useState('')
  const results = useQuery({
    queryKey: ['search', q],
    queryFn: () => api<SearchResponse>(`/search?${new URLSearchParams({ q })}`),
    enabled: q.length > 0,
  })
  return (
    <Card className="mb-6 p-4">
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          setQ(input.trim())
        }}
      >
        <Input type="search" aria-label="Search knowledge" placeholder="Search the knowledge you can access…" value={input} onChange={(e) => setInput(e.target.value)} />
        <Button type="submit" variant="secondary" disabled={!input.trim()}>
          Search
        </Button>
      </form>
      {q && (
        <div className="mt-4">
          {results.isPending ? (
            <Loading label="Searching…" />
          ) : results.isError ? (
            <ErrorState error={results.error} />
          ) : results.data.hits.length === 0 ? (
            <EmptyState title="No matching passages">Only collections you have access to are searched.</EmptyState>
          ) : (
            <>
              <p className="mb-2 text-xs text-slate-500">
                {results.data.hits.length} passages · {results.data.latency_ms} ms · {results.data.embedding_model}
                {!results.data.has_evidence && ' · weak match: a draft would report insufficient evidence'}
              </p>
              <ol className="space-y-2" aria-label="Search results">
                {results.data.hits.map((h) => (
                  <li key={h.chunk_id} className="rounded-md bg-slate-50 p-3 text-sm ring-1 ring-slate-200">
                    <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                      <Link to={`/documents/${h.document_id}`} className="font-medium text-slate-700 hover:text-indigo-700">
                        {h.document_title}
                      </Link>
                      {sectionLabel(h.document_title, h.heading) && <span>› {sectionLabel(h.document_title, h.heading)}</span>}
                      <Badge>{h.collection_name}</Badge>
                      {h.similarity !== null && <span>similarity {h.similarity.toFixed(2)}</span>}
                      {h.keyword_rank !== null && <span>keyword #{h.keyword_rank}</span>}
                    </div>
                    <p className="line-clamp-3 whitespace-pre-wrap text-slate-700">{h.text}</p>
                  </li>
                ))}
              </ol>
            </>
          )}
        </div>
      )}
    </Card>
  )
}

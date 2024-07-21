import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { api } from '../api/client'
import type { Collection } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { Button, Card, EmptyState, ErrorState, InlineError, Input, Label, Loading, PageHeader } from '../components/ui'

export function CollectionsPage() {
  const { user } = useAuth()
  const collections = useQuery({ queryKey: ['collections'], queryFn: () => api<Collection[]>('/collections') })
  const [showForm, setShowForm] = useState(false)
  const isAdmin = user?.role === 'admin'

  return (
    <>
      <PageHeader
        title="Knowledge"
        description={isAdmin ? 'All collections. Grants decide which agents can retrieve from each one.' : 'Collections you can read. Drafts only ever cite these.'}
        actions={isAdmin && <Button onClick={() => setShowForm((v) => !v)}>{showForm ? 'Close' : 'New collection'}</Button>}
      />
      {showForm && <CreateCollectionForm onDone={() => setShowForm(false)} />}
      {collections.isPending ? (
        <Loading />
      ) : collections.isError ? (
        <ErrorState error={collections.error} onRetry={() => void collections.refetch()} />
      ) : collections.data.length === 0 ? (
        <EmptyState title="No collections available">
          {isAdmin ? 'Create a collection to start uploading documents.' : 'Ask an admin to grant you access to a knowledge collection.'}
        </EmptyState>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {collections.data.map((c) => (
            <Link key={c.id} to={`/collections/${c.id}`} className="group">
              <Card className="h-full p-4 transition group-hover:ring-indigo-300">
                <h2 className="font-semibold group-hover:text-indigo-700">{c.name}</h2>
                <p className="mt-1 line-clamp-2 text-sm text-slate-500">{c.description || 'No description'}</p>
                <p className="mt-3 text-xs text-slate-400">
                  {c.document_count} document{c.document_count === 1 ? '' : 's'}
                </p>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </>
  )
}

function CreateCollectionForm({ onDone }: { onDone: () => void }) {
  const qc = useQueryClient()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const create = useMutation({
    mutationFn: () => api<Collection>('/collections', { method: 'POST', json: { name, description } }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['collections'] })
      onDone()
    },
  })
  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    create.mutate()
  }
  return (
    <Card className="mb-6 p-4">
      <form onSubmit={onSubmit} className="grid gap-4 sm:grid-cols-[1fr_2fr_auto] sm:items-end">
        <div>
          <Label htmlFor="nc-name">Name</Label>
          <Input id="nc-name" required value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div>
          <Label htmlFor="nc-desc">Description</Label>
          <Input id="nc-desc" value={description} onChange={(e) => setDescription(e.target.value)} />
        </div>
        <Button type="submit" loading={create.isPending}>
          Create
        </Button>
      </form>
      <InlineError error={create.error} />
    </Card>
  )
}

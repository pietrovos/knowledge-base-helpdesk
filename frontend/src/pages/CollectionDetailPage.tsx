import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { api } from '../api/client'
import type { Collection, Grant, Group, User } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { Badge, Button, Card, ErrorState, InlineError, Loading, PageHeader, Select } from '../components/ui'

export function CollectionDetailPage() {
  const { collectionId } = useParams()
  const id = Number(collectionId)
  const { user } = useAuth()
  const collection = useQuery({ queryKey: ['collections', id], queryFn: () => api<Collection>(`/collections/${id}`) })

  if (collection.isPending) return <Loading />
  if (collection.isError) return <ErrorState error={collection.error} onRetry={() => void collection.refetch()} />

  return (
    <>
      <Link to="/collections" className="text-sm text-slate-500 hover:text-slate-700">
        ← Knowledge
      </Link>
      <PageHeader title={collection.data.name} description={collection.data.description} />
      <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
        <section aria-label="Documents" />
        {user?.role === 'admin' && <AccessPanel collectionId={id} />}
      </div>
    </>
  )
}

function AccessPanel({ collectionId }: { collectionId: number }) {
  const qc = useQueryClient()
  const key = ['collections', collectionId, 'grants']
  const grants = useQuery({ queryKey: key, queryFn: () => api<Grant[]>(`/collections/${collectionId}/grants`) })
  const groups = useQuery({ queryKey: ['groups'], queryFn: () => api<Group[]>('/groups') })
  const users = useQuery({ queryKey: ['users'], queryFn: () => api<User[]>('/users') })
  const [principal, setPrincipal] = useState('')

  const add = useMutation({
    mutationFn: () => {
      const [kind, pid] = principal.split(':')
      return api<Grant>(`/collections/${collectionId}/grants`, {
        method: 'POST',
        json: kind === 'g' ? { group_id: Number(pid) } : { user_id: Number(pid) },
      })
    },
    onSuccess: () => {
      setPrincipal('')
      void qc.invalidateQueries({ queryKey: key })
    },
  })
  const revoke = useMutation({
    mutationFn: (grantId: number) => api(`/collections/${collectionId}/grants/${grantId}`, { method: 'DELETE' }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: key }),
  })

  const granted = new Set((grants.data ?? []).map((g) => (g.group ? `g:${g.group.id}` : `u:${g.user!.id}`)))

  return (
    <Card className="h-fit p-4" >
      <h2 className="font-semibold">Access</h2>
      <p className="mt-1 text-xs text-slate-500">Revoking access removes this collection from retrieval on the very next request.</p>
      {grants.isPending ? (
        <Loading />
      ) : grants.isError ? (
        <ErrorState error={grants.error} />
      ) : (
        <ul className="mt-3 divide-y divide-slate-100" aria-label="Grants">
          {grants.data.length === 0 && <li className="py-2 text-sm text-slate-500">Admins only</li>}
          {grants.data.map((g) => (
            <li key={g.id} className="flex items-center justify-between gap-2 py-2 text-sm">
              <span className="flex min-w-0 items-center gap-2">
                <Badge tone={g.group ? 'indigo' : 'slate'}>{g.group ? 'Group' : 'User'}</Badge>
                <span className="truncate">{g.group?.name ?? g.user?.name}</span>
              </span>
              <Button size="sm" variant="danger" onClick={() => revoke.mutate(g.id)} aria-label={`Revoke ${g.group?.name ?? g.user?.name}`}>
                Revoke
              </Button>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-3 flex gap-2">
        <Select aria-label="Grant access to" value={principal} onChange={(e) => setPrincipal(e.target.value)}>
          <option value="">Grant access to…</option>
          <optgroup label="Groups">
            {(groups.data ?? []).filter((g) => !granted.has(`g:${g.id}`)).map((g) => (
              <option key={g.id} value={`g:${g.id}`}>
                {g.name}
              </option>
            ))}
          </optgroup>
          <optgroup label="Users">
            {(users.data ?? []).filter((u) => u.is_active && !granted.has(`u:${u.id}`)).map((u) => (
              <option key={u.id} value={`u:${u.id}`}>
                {u.name}
              </option>
            ))}
          </optgroup>
        </Select>
        <Button variant="secondary" disabled={!principal} loading={add.isPending} onClick={() => add.mutate()}>
          Grant
        </Button>
      </div>
      <InlineError error={add.error ?? revoke.error} />
    </Card>
  )
}

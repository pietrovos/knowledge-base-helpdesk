import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { api } from '../../api/client'
import type { Group, User } from '../../api/types'
import { Button, Card, EmptyState, ErrorState, InlineError, Input, Label, Loading, PageHeader, Select } from '../../components/ui'

export function GroupsPage() {
  const groups = useQuery({ queryKey: ['groups'], queryFn: () => api<Group[]>('/groups') })
  const users = useQuery({ queryKey: ['users'], queryFn: () => api<User[]>('/users') })
  const [showForm, setShowForm] = useState(false)

  return (
    <>
      <PageHeader
        title="Groups"
        description="Grant knowledge collections to groups instead of individuals."
        actions={<Button onClick={() => setShowForm((v) => !v)}>{showForm ? 'Close' : 'New group'}</Button>}
      />
      {showForm && <CreateGroupForm onDone={() => setShowForm(false)} />}
      {groups.isPending ? (
        <Loading />
      ) : groups.isError ? (
        <ErrorState error={groups.error} onRetry={() => void groups.refetch()} />
      ) : groups.data.length === 0 ? (
        <EmptyState title="No groups yet">Create a group, add agents, then grant it collections.</EmptyState>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {groups.data.map((g) => (
            <GroupCard key={g.id} group={g} users={users.data ?? []} />
          ))}
        </div>
      )}
    </>
  )
}

function GroupCard({ group, users }: { group: Group; users: User[] }) {
  const qc = useQueryClient()
  const [userId, setUserId] = useState('')
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ['groups'] })
    void qc.invalidateQueries({ queryKey: ['users'] })
  }
  const add = useMutation({
    mutationFn: () => api<Group>(`/groups/${group.id}/members`, { method: 'POST', json: { user_id: Number(userId) } }),
    onSuccess: () => {
      setUserId('')
      refresh()
    },
  })
  const remove = useMutation({
    mutationFn: (uid: number) => api<Group>(`/groups/${group.id}/members/${uid}`, { method: 'DELETE' }),
    onSuccess: refresh,
  })
  const del = useMutation({ mutationFn: () => api(`/groups/${group.id}`, { method: 'DELETE' }), onSuccess: refresh })
  const candidates = users.filter((u) => u.is_active && !group.members.some((m) => m.id === u.id))

  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="font-semibold">{group.name}</h2>
          {group.description && <p className="text-sm text-slate-500">{group.description}</p>}
        </div>
        <Button size="sm" variant="ghost" onClick={() => confirm(`Delete group "${group.name}"?`) && del.mutate()}>
          Delete
        </Button>
      </div>
      <ul className="mt-3 divide-y divide-slate-100">
        {group.members.length === 0 && <li className="py-2 text-sm text-slate-500">No members</li>}
        {group.members.map((m) => (
          <li key={m.id} className="flex items-center justify-between py-2 text-sm">
            <span>
              {m.name} <span className="text-slate-400">· {m.email}</span>
            </span>
            <Button size="sm" variant="ghost" onClick={() => remove.mutate(m.id)} aria-label={`Remove ${m.name}`}>
              Remove
            </Button>
          </li>
        ))}
      </ul>
      <div className="mt-3 flex gap-2">
        <Select aria-label={`Add member to ${group.name}`} value={userId} onChange={(e) => setUserId(e.target.value)}>
          <option value="">Add member…</option>
          {candidates.map((u) => (
            <option key={u.id} value={u.id}>
              {u.name}
            </option>
          ))}
        </Select>
        <Button variant="secondary" disabled={!userId} loading={add.isPending} onClick={() => add.mutate()}>
          Add
        </Button>
      </div>
      <InlineError error={add.error ?? remove.error ?? del.error} />
    </Card>
  )
}

function CreateGroupForm({ onDone }: { onDone: () => void }) {
  const qc = useQueryClient()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const create = useMutation({
    mutationFn: () => api<Group>('/groups', { method: 'POST', json: { name, description } }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['groups'] })
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
          <Label htmlFor="ng-name">Name</Label>
          <Input id="ng-name" required value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div>
          <Label htmlFor="ng-desc">Description</Label>
          <Input id="ng-desc" value={description} onChange={(e) => setDescription(e.target.value)} />
        </div>
        <Button type="submit" loading={create.isPending}>
          Create group
        </Button>
      </form>
      <InlineError error={create.error} />
    </Card>
  )
}

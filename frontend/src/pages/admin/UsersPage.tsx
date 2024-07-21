import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { api } from '../../api/client'
import type { Role, User } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { Badge, Button, Card, EmptyState, ErrorState, InlineError, Input, Label, Loading, PageHeader, Select } from '../../components/ui'

export function UsersPage() {
  const qc = useQueryClient()
  const { user: me } = useAuth()
  const users = useQuery({ queryKey: ['users'], queryFn: () => api<User[]>('/users') })
  const update = useMutation({
    mutationFn: ({ id, ...patch }: { id: number; role?: Role; is_active?: boolean }) =>
      api<User>(`/users/${id}`, { method: 'PATCH', json: patch }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  })
  const [showForm, setShowForm] = useState(false)

  return (
    <>
      <PageHeader
        title="Users"
        description="Agents answer tickets; admins also manage people, groups and knowledge access."
        actions={<Button onClick={() => setShowForm((v) => !v)}>{showForm ? 'Close' : 'Add user'}</Button>}
      />
      {showForm && <CreateUserForm onDone={() => setShowForm(false)} />}
      <InlineError error={update.error} />
      {users.isPending ? (
        <Loading />
      ) : users.isError ? (
        <ErrorState error={users.error} onRetry={() => void users.refetch()} />
      ) : users.data.length === 0 ? (
        <EmptyState title="No users yet" />
      ) : (
        <Card className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs font-semibold tracking-wide text-slate-500 uppercase">
              <tr>
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Groups</th>
                <th className="px-4 py-3">Role</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {users.data.map((u) => (
                <tr key={u.id} className={u.is_active ? '' : 'text-slate-400'}>
                  <td className="px-4 py-3">
                    <div className="font-medium">{u.name}</div>
                    <div className="text-xs text-slate-500">{u.email}</div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {u.groups.length ? u.groups.map((g) => <Badge key={g.id}>{g.name}</Badge>) : '—'}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <Select
                      aria-label={`Role for ${u.name}`}
                      value={u.role}
                      disabled={u.id === me?.id}
                      onChange={(e) => update.mutate({ id: u.id, role: e.target.value as Role })}
                      className="min-w-28"
                    >
                      <option value="agent">Agent</option>
                      <option value="admin">Admin</option>
                    </Select>
                  </td>
                  <td className="px-4 py-3">{u.is_active ? <Badge tone="green">Active</Badge> : <Badge>Deactivated</Badge>}</td>
                  <td className="px-4 py-3 text-right">
                    {u.id !== me?.id && (
                      <Button size="sm" variant={u.is_active ? 'danger' : 'secondary'} onClick={() => update.mutate({ id: u.id, is_active: !u.is_active })}>
                        {u.is_active ? 'Deactivate' : 'Reactivate'}
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </>
  )
}

function CreateUserForm({ onDone }: { onDone: () => void }) {
  const qc = useQueryClient()
  const [form, setForm] = useState({ name: '', email: '', password: '', role: 'agent' as Role })
  const create = useMutation({
    mutationFn: () => api<User>('/users', { method: 'POST', json: form }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['users'] })
      onDone()
    },
  })
  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    create.mutate()
  }
  return (
    <Card className="mb-6 p-4">
      <form onSubmit={onSubmit} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5 lg:items-end">
        <div>
          <Label htmlFor="nu-name">Name</Label>
          <Input id="nu-name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </div>
        <div>
          <Label htmlFor="nu-email">Email</Label>
          <Input id="nu-email" type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        </div>
        <div>
          <Label htmlFor="nu-pass">Temporary password</Label>
          <Input id="nu-pass" type="password" minLength={8} required value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
        </div>
        <div>
          <Label htmlFor="nu-role">Role</Label>
          <Select id="nu-role" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Role })}>
            <option value="agent">Agent</option>
            <option value="admin">Admin</option>
          </Select>
        </div>
        <Button type="submit" loading={create.isPending}>
          Create user
        </Button>
      </form>
      <InlineError error={create.error} />
    </Card>
  )
}

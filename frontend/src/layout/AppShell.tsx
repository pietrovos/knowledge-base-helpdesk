import { useQuery } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import { NavLink, Navigate, Outlet, useLocation } from 'react-router'
import { api } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Loading, cx } from '../components/ui'

interface NavItem {
  to: string
  label: string
  adminOnly?: boolean
  count?: 'escalated' | 'gaps'
}

const NAV: NavItem[] = [
  { to: '/tickets', label: 'Inbox' },
  { to: '/escalations', label: 'Escalations', count: 'escalated' },
  { to: '/knowledge-gaps', label: 'Knowledge gaps', count: 'gaps' },
  { to: '/collections', label: 'Knowledge' },
  { to: '/admin/users', label: 'Users', adminOnly: true },
  { to: '/admin/groups', label: 'Groups', adminOnly: true },
]

function Logo() {
  return (
    <div className="flex items-center gap-2 px-2">
      <img src="/favicon.svg" alt="" className="size-7" />
      <span className="text-base font-semibold tracking-tight text-white">SupportLens</span>
    </div>
  )
}

export function AppShell({ banner }: { banner?: ReactNode }) {
  const { user, isLoading, logout } = useAuth()
  const location = useLocation()
  const [open, setOpen] = useState(false)
  const ticketCounts = useQuery({ queryKey: ['tickets', 'counts'], queryFn: () => api<Record<string, number>>('/tickets/counts'), enabled: !!user, refetchInterval: 30_000 })
  const gapCounts = useQuery({ queryKey: ['knowledge-gaps', 'counts'], queryFn: () => api<Record<string, number>>('/knowledge-gaps/counts'), enabled: !!user, refetchInterval: 30_000 })

  if (isLoading) return <Loading />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />

  const items = NAV.filter((n) => !n.adminOnly || user.role === 'admin')
  const counts = { escalated: ticketCounts.data?.escalated, gaps: gapCounts.data?.open }
  const nav = (
    <nav className="flex flex-1 flex-col gap-1" aria-label="Main">
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          onClick={() => setOpen(false)}
          className={({ isActive }) =>
            cx(
              'rounded-md px-3 py-2 text-sm font-medium',
              isActive ? 'bg-slate-800 text-white' : 'text-slate-300 hover:bg-slate-800/60 hover:text-white',
            )
          }
        >
          <span className="flex items-center justify-between">
            {item.label}
            {item.count && !!counts[item.count] && <span className="rounded-full bg-slate-700 px-2 text-xs text-white">{counts[item.count]}</span>}
          </span>
        </NavLink>
      ))}
    </nav>
  )
  const footer = (
    <div className="border-t border-slate-800 pt-4">
      <p className="truncate px-3 text-sm font-medium text-white">{user.name}</p>
      <p className="truncate px-3 text-xs text-slate-400">
        {user.email} · {user.role}
      </p>
      <button onClick={() => void logout()} className="mt-2 px-3 text-xs font-medium text-slate-300 hover:text-white">
        Sign out
      </button>
    </div>
  )

  return (
    <div className="flex min-h-full">
      <aside className="hidden w-60 shrink-0 flex-col gap-6 bg-slate-900 p-4 lg:flex">
        <Logo />
        {nav}
        {footer}
      </aside>

      {open && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true">
          <div className="absolute inset-0 bg-slate-900/60" onClick={() => setOpen(false)} />
          <aside className="relative flex h-full w-64 flex-col gap-6 bg-slate-900 p-4">
            <Logo />
            {nav}
            {footer}
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-slate-200 bg-white px-4 py-3 lg:hidden">
          <button onClick={() => setOpen(true)} className="rounded-md p-1.5 text-slate-600 hover:bg-slate-100" aria-label="Open menu">
            <svg className="size-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path fillRule="evenodd" d="M2 4.75A.75.75 0 0 1 2.75 4h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 4.75Zm0 5.25a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 10Zm.75 4.5a.75.75 0 0 0 0 1.5h14.5a.75.75 0 0 0 0-1.5H2.75Z" clipRule="evenodd" />
            </svg>
          </button>
          <span className="font-semibold">SupportLens</span>
        </header>
        {banner}
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6 lg:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export function RequireAdmin({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  if (user?.role !== 'admin') return <Navigate to="/" replace />
  return children
}

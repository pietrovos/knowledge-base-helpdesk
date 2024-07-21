import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createContext, use, type ReactNode } from 'react'
import { ApiError, api } from '../api/client'
import type { User } from '../api/types'

interface AuthValue {
  user: User | null
  isLoading: boolean
  login: (email: string, password: string) => Promise<User>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient()
  const me = useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      try {
        return await api<User>('/auth/me')
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) return null
        throw e
      }
    },
    staleTime: 60_000,
  })

  // Cached data belongs to whoever was signed in; drop it all except the session query itself
  // (clearing that would detach the observer above).
  const dropOtherUsersData = () => qc.removeQueries({ predicate: (q) => q.queryKey[0] !== 'me' })

  const value: AuthValue = {
    user: me.data ?? null,
    isLoading: me.isPending,
    login: async (email, password) => {
      const user = await api<User>('/auth/login', { method: 'POST', json: { email, password } })
      dropOtherUsersData()
      qc.setQueryData(['me'], user)
      return user
    },
    logout: async () => {
      await api('/auth/logout', { method: 'POST' })
      dropOtherUsersData()
      qc.setQueryData(['me'], null)
    },
  }
  return <AuthContext value={value}>{children}</AuthContext>
}

export function useAuth() {
  const ctx = use(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}

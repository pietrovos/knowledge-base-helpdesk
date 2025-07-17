import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import type { SystemStatus } from '../api/types'

export function useSystemStatus(enabled = true) {
  return useQuery({
    queryKey: ['system', 'status'],
    queryFn: () => api<SystemStatus>('/system/status'),
    enabled,
    refetchInterval: (q) => (q.state.data && !q.state.data.drafting_available ? 5_000 : 20_000),
  })
}

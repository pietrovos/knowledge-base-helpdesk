import { useQuery } from '@tanstack/react-query'
import { api } from './api/client'

export default function App() {
  const health = useQuery({ queryKey: ['health'], queryFn: () => api<{ status: string }>('/health') })
  return (
    <main className="mx-auto max-w-xl p-8">
      <h1 className="text-2xl font-semibold">SupportLens</h1>
      <p className="mt-2 text-slate-600" data-testid="api-status">
        API: {health.isPending ? 'checking…' : health.isError ? 'unreachable' : health.data.status}
      </p>
    </main>
  )
}

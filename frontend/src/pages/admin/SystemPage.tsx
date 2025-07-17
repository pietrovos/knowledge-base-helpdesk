import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/client'
import type { SystemStatus } from '../../api/types'
import { Badge, Button, Card, ErrorState, InlineError, Loading, PageHeader } from '../../components/ui'
import { useSystemStatus } from '../../components/useSystemStatus'

const DRILLS: { mode: SystemStatus['llm']['simulated_outage']; label: string; help: string }[] = [
  { mode: 'error', label: 'Provider errors', help: 'Every model call fails with a 503. The circuit opens after 3 failures.' },
  { mode: 'timeout', label: 'Provider hangs', help: 'Calls never answer; the deadline cuts them off and counts a failure.' },
  { mode: 'slow', label: 'Provider slow', help: 'Calls succeed after a long delay. Drafts arrive late but correctly.' },
]

export function SystemPage() {
  const qc = useQueryClient()
  const status = useSystemStatus()
  const setMode = useMutation({
    mutationFn: (mode: string) => api<SystemStatus>('/system/chaos', { method: 'PUT', json: { mode } }),
    onSuccess: (data) => qc.setQueryData(['system', 'status'], data),
  })
  if (status.isPending) return <Loading />
  if (status.isError) return <ErrorState error={status.error} onRetry={() => void status.refetch()} />
  const s = status.data
  const stateTone = s.llm.state === 'closed' ? 'green' : s.llm.state === 'open' ? 'red' : 'amber'

  return (
    <>
      <PageHeader title="System" description="Provider health and outage drills." />
      <div className="grid gap-4 md:grid-cols-3">
        <Card className="p-4">
          <p className="text-xs text-slate-500 uppercase">Model provider</p>
          <p className="mt-1 font-medium">
            {s.llm.provider} · {s.llm.model}
          </p>
          <p className="mt-2 flex items-center gap-2 text-sm">
            Circuit <Badge tone={stateTone}>{s.llm.state.replace('_', '-')}</Badge>
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {s.llm.recent_failures} recent failure{s.llm.recent_failures === 1 ? '' : 's'}
            {s.llm.retry_in_seconds !== null && s.llm.state === 'open' && ` · retry in ${s.llm.retry_in_seconds}s`}
          </p>
          {s.llm.last_error && <p className="mt-1 truncate text-xs text-red-600">{s.llm.last_error}</p>}
        </Card>
        <Card className="p-4">
          <p className="text-xs text-slate-500 uppercase">Background workers</p>
          <p className="mt-2">{s.worker_online ? <Badge tone="green">Online</Badge> : <Badge tone="red">Offline</Badge>}</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-slate-500 uppercase">Embeddings</p>
          <p className="mt-1 font-medium">{s.embedding_provider}</p>
        </Card>
      </div>

      <h2 className="mt-8 mb-1 font-semibold">Provider outage drill</h2>
      <p className="mb-3 text-sm text-slate-500">Simulate a failing model provider for everyone (auto-expires after an hour). Use it to check that tickets stay fully usable.</p>
      <div className="grid gap-3 md:grid-cols-3">
        {DRILLS.map((d) => {
          const active = s.llm.simulated_outage === d.mode
          return (
            <Card key={d.mode} className={active ? 'p-4 ring-2 ring-amber-400' : 'p-4'}>
              <p className="font-medium">{d.label}</p>
              <p className="mt-1 text-xs text-slate-500">{d.help}</p>
              <Button className="mt-3" size="sm" variant={active ? 'danger' : 'secondary'} loading={setMode.isPending && setMode.variables === d.mode} onClick={() => setMode.mutate(active ? 'none' : d.mode)}>
                {active ? 'Stop drill' : 'Start drill'}
              </Button>
            </Card>
          )
        })}
      </div>
      {s.llm.simulated_outage !== 'none' || s.llm.state !== 'closed' ? (
        <Button className="mt-4" variant="secondary" onClick={() => setMode.mutate('none')}>
          End drill and reset circuit
        </Button>
      ) : null}
      <InlineError error={setMode.error} />
    </>
  )
}

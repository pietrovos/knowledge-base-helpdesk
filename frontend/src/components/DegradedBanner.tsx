import { useSystemStatus } from './useSystemStatus'

export function DegradedBanner() {
  const status = useSystemStatus()
  const s = status.data
  if (!s?.degraded_reasons?.length) return null
  return (
    <div role="status" data-testid="degraded-banner" className="border-b border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-amber-900 sm:px-6 lg:px-8">
      <span className="font-semibold">Degraded mode.</span> {s.degraded_reasons.join(' ')} Tickets, search and manual replies work normally.
      {s.llm.retry_in_seconds !== null && s.llm.state === 'open' && <span className="text-amber-700"> Drafting resumes with a trial request in ~{s.llm.retry_in_seconds}s.</span>}
    </div>
  )
}

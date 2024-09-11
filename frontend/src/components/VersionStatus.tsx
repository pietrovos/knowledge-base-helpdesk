import type { DocVersion } from '../api/types'
import { Badge, type Tone } from './ui'

const tone: Record<DocVersion['status'], Tone> = {
  queued: 'slate',
  processing: 'blue',
  ready: 'green',
  superseded: 'slate',
  failed: 'red',
}

export const isBusy = (v: DocVersion | null | undefined) => !!v && (v.status === 'queued' || v.status === 'processing')

export function VersionStatusBadge({ version }: { version: DocVersion }) {
  const label = version.status === 'ready' ? 'Live' : version.stage === 'retrying' ? 'Retrying' : version.status[0].toUpperCase() + version.status.slice(1)
  return <Badge tone={version.stage === 'retrying' ? 'amber' : tone[version.status]}>{label}</Badge>
}

export function VersionProgress({ version }: { version: DocVersion }) {
  if (!isBusy(version)) return null
  return (
    <div className="mt-2" aria-label={`Processing v${version.version}`}>
      <div className="flex justify-between text-xs text-slate-500">
        <span className="capitalize">{version.stage}</span>
        <span>{version.progress}%</span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-100" role="progressbar" aria-valuenow={version.progress} aria-valuemin={0} aria-valuemax={100}>
        <div className="h-full rounded-full bg-indigo-500 transition-all" style={{ width: `${Math.max(4, version.progress)}%` }} />
      </div>
    </div>
  )
}

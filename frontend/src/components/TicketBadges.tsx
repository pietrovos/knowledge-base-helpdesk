import type { TicketPriority, TicketStatus } from '../api/types'
import { Badge, type Tone } from './ui'

const statusTone: Record<TicketStatus, Tone> = { open: 'blue', pending: 'amber', escalated: 'red', resolved: 'green', closed: 'slate' }
const priorityTone: Record<TicketPriority, Tone> = { low: 'slate', normal: 'slate', high: 'amber', urgent: 'red' }

export const cap = (s: string) => s[0].toUpperCase() + s.slice(1)

export function StatusBadge({ status }: { status: TicketStatus }) {
  return <Badge tone={statusTone[status]}>{cap(status)}</Badge>
}

export function PriorityBadge({ priority }: { priority: TicketPriority }) {
  if (priority === 'normal') return null
  return <Badge tone={priorityTone[priority]}>{cap(priority)}</Badge>
}

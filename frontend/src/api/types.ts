export type Role = 'agent' | 'admin'

export interface GroupRef {
  id: number
  name: string
}

export interface UserRef {
  id: number
  name: string
  email: string
}

export interface User extends UserRef {
  role: Role
  is_active: boolean
  groups: GroupRef[]
}

export interface Group {
  id: number
  name: string
  description: string
  members: UserRef[]
}

export interface Collection {
  id: number
  name: string
  description: string
  created_at: string
  document_count: number
}

export interface Grant {
  id: number
  collection_id: number
  user: UserRef | null
  group: GroupRef | null
  created_at: string
}

export type VersionStatus = 'queued' | 'processing' | 'ready' | 'superseded' | 'failed'

export interface DocVersion {
  id: number
  version: number
  status: VersionStatus
  progress: number
  stage: string
  error: string | null
  attempts: number
  chunk_count: number
  size_bytes: number
  sha256: string
  embedding_model: string | null
  created_at: string
  processed_at: string | null
}

export interface DocumentSummary {
  id: number
  collection_id: number
  title: string
  filename: string
  created_at: string
  current_version: DocVersion | null
  latest_version: DocVersion | null
}

export interface DocumentDetail extends DocumentSummary {
  collection_name: string
  versions: DocVersion[]
}

export interface UploadResult {
  document: DocumentSummary
  version: DocVersion
  created: boolean
  queued: boolean
}

export interface ChunkRow {
  id: number
  ordinal: number
  heading: string
  text: string
  char_start: number
  char_end: number
  is_active: boolean
}

export type TicketStatus = 'open' | 'pending' | 'escalated' | 'resolved' | 'closed'
export type TicketPriority = 'low' | 'normal' | 'high' | 'urgent'
export type InboxView = 'active' | 'mine' | 'unassigned' | 'pending' | 'escalated' | 'resolved' | 'closed' | 'all'

export interface TicketSummary {
  id: number
  subject: string
  customer_name: string
  customer_email: string
  status: TicketStatus
  priority: TicketPriority
  assignee: UserRef | null
  created_at: string
  updated_at: string
  preview: string
  message_count: number
}

export interface TicketMessage {
  id: number
  author_type: 'customer' | 'agent'
  author: UserRef | null
  body: string
  is_internal: boolean
  draft_id: number | null
  created_at: string
}

export interface TicketEvent {
  id: number
  kind: string
  actor: UserRef | null
  data: Record<string, unknown>
  created_at: string
}

export interface TicketDetail extends TicketSummary {
  escalation_reason: string | null
  messages: TicketMessage[]
  events: TicketEvent[]
}

export interface TicketPage {
  items: TicketSummary[]
  total: number
  page: number
  page_size: number
}

export interface SearchHit {
  chunk_id: number
  document_id: number
  document_title: string
  collection_name: string
  version: number
  heading: string
  text: string
  similarity: number | null
  keyword_rank: number | null
  score: number
}

export interface SearchResponse {
  query: string
  hits: SearchHit[]
  has_evidence: boolean
  embedding_model: string
  latency_ms: number
}

export type DraftStatus = 'pending' | 'ready' | 'insufficient_evidence' | 'failed' | 'published' | 'discarded'

export interface DraftSource {
  chunk_id: number
  document_id: number
  document_title: string
  version: number
  heading: string
  text: string | null
  rank: number
  similarity: number | null
  keyword_rank: number | null
  cited: boolean
  accessible: boolean
  live: boolean
}

export interface Draft {
  id: number
  ticket_id: number
  status: DraftStatus
  question: string
  custom_question: boolean
  reply: string
  missing_information: string
  invalid_citation_ids: number[]
  error: string | null
  error_kind: string | null
  decided_by: 'model' | 'evidence_gate' | 'validator' | null
  provider: string | null
  model: string | null
  embedding_model: string | null
  retrieval_ms: number | null
  generation_ms: number | null
  best_similarity: number | null
  requested_by: UserRef | null
  created_at: string
  completed_at: string | null
  published_text: string | null
  was_edited: boolean | null
  sources: DraftSource[]
  knowledge_gap_id: number | null
}

export interface Evidence {
  source: DraftSource
  context_before: string | null
  context_after: string | null
  collection_name: string
}

export interface KnowledgeGap {
  id: number
  ticket_id: number | null
  draft_id: number | null
  question: string
  missing_information: string
  status: 'open' | 'resolved' | 'dismissed'
  created_by: UserRef | null
  resolved_by: UserRef | null
  resolution_note: string | null
  resolved_document_id: number | null
  created_at: string
  resolved_at: string | null
}

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

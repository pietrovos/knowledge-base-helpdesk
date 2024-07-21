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

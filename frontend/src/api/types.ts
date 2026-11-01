export type Role = 'attendee' | 'organizer' | 'admin'
export type EventStatus = 'draft' | 'published' | 'finished' | 'cancelled'

export interface User {
  id: string
  email: string
  full_name: string
  role: Role
  is_active: boolean
}

export interface AppEvent {
  id: string
  name: string
  description: string | null
  location: string
  start_at: string
  end_at: string
  capacity: number
  registered_count: number
  available_slots: number
  status: EventStatus
  organizer_id: string
  closed_at: string | null
  closed_by_id: string | null
  closed_source: 'manual' | 'scheduler' | null
  created_at: string
  updated_at: string
}

export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface SpeakerSummary {
  id: string
  name: string
  bio: string | null
}

export interface Speaker extends SpeakerSummary {
  email: string | null
  created_by_id: string
  created_at: string
}

export interface AgendaSession {
  id: string
  event_id: string
  title: string
  description: string | null
  start_at: string
  end_at: string
  capacity: number
  registered_count: number
  available_slots: number
  speaker: SpeakerSummary | null
}

export interface MyRegistration {
  event: AppEvent
  registered_at: string
  sessions: AgendaSession[]
}

export interface Attendee {
  registration_id: string
  user_id: string
  full_name: string
  email: string
  registered_at: string
}

export interface ErrorBody {
  code: string
  message: string
  details?: string[]
}

export interface EventInput {
  name: string
  description: string | null
  location: string
  start_at: string
  end_at: string
  capacity: number
}

export interface SessionInput {
  speaker_id: string
  title: string
  description: string | null
  start_at: string
  end_at: string
  capacity: number
}

export interface SpeakerInput {
  name: string
  email: string | null
  bio: string | null
}

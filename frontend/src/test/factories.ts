import type {
  AgendaSession,
  AppEvent,
  Attendee,
  MyRegistration,
  Role,
  Speaker,
  User,
} from '@/api/types'

let counter = 0
const next = () => ++counter

export function makeUser(overrides: Partial<User> = {}): User {
  const n = next()
  return {
    id: `user-${n}`,
    email: `user${n}@example.com`,
    full_name: `Usuario ${n}`,
    role: 'attendee',
    is_active: true,
    ...overrides,
  }
}

export const makeUserWithRole = (role: Role, overrides: Partial<User> = {}) =>
  makeUser({ role, ...overrides })

export function makeEvent(overrides: Partial<AppEvent> = {}): AppEvent {
  const n = next()
  const capacity = overrides.capacity ?? 50
  const registered = overrides.registered_count ?? 0
  return {
    id: `event-${n}`,
    name: `Congreso ${n}`,
    description: 'Una descripción del evento.',
    location: 'Bogotá',
    start_at: '2030-05-10T14:00:00Z',
    end_at: '2030-05-10T22:00:00Z',
    capacity,
    registered_count: registered,
    available_slots: capacity - registered,
    status: 'published',
    organizer_id: 'organizer-1',
    closed_at: null,
    closed_by_id: null,
    closed_source: null,
    created_at: '2030-01-01T00:00:00Z',
    updated_at: '2030-01-01T00:00:00Z',
    ...overrides,
  }
}

export function makeSession(overrides: Partial<AgendaSession> = {}): AgendaSession {
  const n = next()
  const capacity = overrides.capacity ?? 20
  const registered = overrides.registered_count ?? 0
  return {
    id: `session-${n}`,
    event_id: 'event-1',
    title: `Sesión ${n}`,
    description: null,
    start_at: '2030-05-10T15:00:00Z',
    end_at: '2030-05-10T16:00:00Z',
    capacity,
    registered_count: registered,
    available_slots: capacity - registered,
    speaker: { id: 'speaker-1', name: 'Ana Pérez', bio: null },
    ...overrides,
  }
}

export function makeSpeaker(overrides: Partial<Speaker> = {}): Speaker {
  const n = next()
  return {
    id: `speaker-${n}`,
    name: `Ponente ${n}`,
    email: `ponente${n}@example.com`,
    bio: null,
    created_by_id: 'organizer-1',
    created_at: '2030-01-01T00:00:00Z',
    ...overrides,
  }
}

export function makeRegistration(event: AppEvent, sessions: AgendaSession[] = []): MyRegistration {
  return { event, registered_at: '2030-02-01T10:00:00Z', sessions }
}

export function makeAttendee(overrides: Partial<Attendee> = {}): Attendee {
  const n = next()
  return {
    registration_id: `reg-${n}`,
    user_id: `user-${n}`,
    full_name: `Asistente ${n}`,
    email: `asistente${n}@example.com`,
    registered_at: '2030-02-01T10:00:00Z',
    ...overrides,
  }
}

export const page = <T>(items: T[], total = items.length, pageNumber = 1, pageSize = 9) => ({
  items,
  total,
  page: pageNumber,
  page_size: pageSize,
})

import { http, HttpResponse } from 'msw'
import { api } from '@/api/client'
import { useAuthStore } from '@/stores/authStore'
import { useRegistrationsStore } from '@/stores/registrationsStore'
import { API } from '@/test/handlers'
import { makeEvent, makeRegistration, makeUser } from '@/test/factories'
import { server } from '@/test/server'

const state = () => useAuthStore.getState()

describe('authStore', () => {
  it('arranca sin saber si hay sesión', () => {
    expect(state()).toMatchObject({ user: null, status: 'unknown' })
  })

  it('loadSession restaura la sesión desde el backend (el token no es legible por JS)', async () => {
    const user = makeUser()
    server.use(http.get(`${API}/auth/me`, () => HttpResponse.json(user)))

    await state().loadSession()

    expect(state()).toMatchObject({ user, status: 'authenticated' })
  })

  it('loadSession sin cookie válida deja al usuario como anónimo', async () => {
    await state().loadSession() // el handler por defecto responde 401

    expect(state()).toMatchObject({ user: null, status: 'anonymous' })
  })

  it('login guarda el usuario y no el token', async () => {
    const user = makeUser()
    server.use(http.post(`${API}/auth/login`, () => HttpResponse.json(user)))

    await state().login(user.email, 'secreto123')

    expect(state().user).toEqual(user)
    expect(JSON.stringify(state())).not.toMatch(/token/i)
  })

  it('un login fallido propaga el error y no cambia el estado', async () => {
    server.use(
      http.post(`${API}/auth/login`, () =>
        HttpResponse.json(
          { code: 'invalid_credentials', message: 'Credenciales inválidas' },
          { status: 401 },
        ),
      ),
    )

    await expect(state().login('a@b.co', 'mala')).rejects.toMatchObject({
      code: 'invalid_credentials',
    })
    expect(state().status).toBe('unknown')
  })

  it('register crea la cuenta y luego inicia sesión', async () => {
    const user = makeUser({ email: 'nuevo@example.com' })
    const calls: string[] = []
    server.use(
      http.post(`${API}/auth/register`, () => {
        calls.push('register')
        return HttpResponse.json(user, { status: 201 })
      }),
      http.post(`${API}/auth/login`, () => {
        calls.push('login')
        return HttpResponse.json(user)
      }),
    )

    await state().register({ email: user.email, password: 'secreto123', full_name: 'Nuevo' })

    expect(calls).toEqual(['register', 'login'])
    expect(state().status).toBe('authenticated')
  })

  it('logout limpia la sesión aunque el servidor falle', async () => {
    useAuthStore.setState({ user: makeUser(), status: 'authenticated' })
    server.use(http.post(`${API}/auth/logout`, () => HttpResponse.error()))

    await state()
      .logout()
      .catch(() => undefined)

    expect(state()).toMatchObject({ user: null, status: 'anonymous' })
  })

  it('clearSession también descarta las inscripciones en memoria', () => {
    useAuthStore.setState({ user: makeUser(), status: 'authenticated' })
    useRegistrationsStore.setState({ items: [makeRegistration(makeEvent())], loaded: true })

    state().clearSession()

    expect(useRegistrationsStore.getState()).toMatchObject({ items: [], loaded: false })
  })

  it('una sesión caducada (401 en otra ruta) cierra la sesión local', async () => {
    useAuthStore.setState({ user: makeUser(), status: 'authenticated' })
    server.use(
      http.get(`${API}/users/me/registrations`, () =>
        HttpResponse.json({ code: 'not_authenticated', message: 'x' }, { status: 401 }),
      ),
    )

    await api.get('/users/me/registrations').catch(() => undefined)

    expect(state().status).toBe('anonymous')
  })
})

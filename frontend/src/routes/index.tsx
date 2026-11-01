import { lazy } from 'react'
import { createBrowserRouter, type RouteObject } from 'react-router-dom'
import { GuestRoute, ProtectedRoute } from '@/routes/guards'
import { RootLayout, RouteError } from '@/routes/RootLayout'

// Cada página se descarga solo cuando se visita (code splitting por ruta).
const EventListPage = lazy(() => import('@/pages/EventListPage'))
const EventDetailPage = lazy(() => import('@/pages/EventDetailPage'))
const EventFormPage = lazy(() => import('@/pages/EventFormPage'))
const LoginPage = lazy(() => import('@/pages/LoginPage'))
const RegisterPage = lazy(() => import('@/pages/RegisterPage'))
const ProfilePage = lazy(() => import('@/pages/ProfilePage'))
const SpeakersPage = lazy(() => import('@/pages/SpeakersPage'))
const AdminUsersPage = lazy(() => import('@/pages/AdminUsersPage'))
const NotFoundPage = lazy(() => import('@/pages/NotFoundPage'))

export const routes: RouteObject[] = [
  {
    path: '/',
    element: <RootLayout />,
    errorElement: <RouteError />,
    children: [
      { index: true, element: <EventListPage /> },
      { path: 'events/:id', element: <EventDetailPage /> },
      {
        element: <GuestRoute />,
        children: [
          { path: 'login', element: <LoginPage /> },
          { path: 'register', element: <RegisterPage /> },
        ],
      },
      {
        element: <ProtectedRoute />,
        children: [{ path: 'profile', element: <ProfilePage /> }],
      },
      {
        element: <ProtectedRoute roles={['organizer', 'admin']} />,
        children: [
          { path: 'events/new', element: <EventFormPage /> },
          { path: 'events/:id/edit', element: <EventFormPage /> },
          { path: 'speakers', element: <SpeakersPage /> },
        ],
      },
      {
        element: <ProtectedRoute roles={['admin']} />,
        children: [{ path: 'admin/users', element: <AdminUsersPage /> }],
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]

export const createAppRouter = () => createBrowserRouter(routes)

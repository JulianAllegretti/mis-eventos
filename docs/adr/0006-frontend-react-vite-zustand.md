# ADR 0006: Frontend con React, Vite, React Router y Zustand

- **Estado:** Propuesto
- **Fecha:** 2026-10-31

## Contexto
El PRD pide React/Vue/Angular, router, manejador de estado, cliente HTTP, componentes reutilizables, tests y, como bonus, lazy loading, WebP y minificación.

## Decisión
- **React 18+ con TypeScript**, empaquetado con **Vite** (minificación y code splitting incluidos).
- **React Router** con rutas cargadas con `React.lazy` y `Suspense`.
- **Zustand** para estado global: `authStore` (usuario y estado de carga de sesión; **no guarda el token**, que vive en una cookie `HttpOnly`, ver ADR 0003) y `eventsStore` (lista, evento actual, paginación, búsqueda).
- **Axios** con `withCredentials: true` y un interceptor que normaliza errores para mostrarlos al usuario; ante un 401 limpia el usuario del `authStore` y redirige a login.
- Al iniciar la app se llama a `GET /auth/me` para restaurar la sesión; las rutas protegidas esperan ese resultado antes de decidir si redirigen.
- Tests con **Vitest + Testing Library** y mocks de red con **MSW**; linting con ESLint y Prettier.
- **Tailwind CSS** (plugin de Vite) y **shadcn/ui** como base de componentes (Radix UI por debajo). Los componentes se copian a `src/components/ui/` con la CLI de shadcn y se mantienen en el repositorio, por lo que se pueden adaptar.
- Responsividad con los breakpoints de Tailwind (enfoque mobile-first); cada página define su layout con ellos.
- Formularios con **react-hook-form** y validación con **zod**; notificaciones con **sonner**; iconos con **lucide-react**.
- Los eventos no tienen imagen propia ni hay subida de archivos. Las imágenes son assets estáticos del diseño, en WebP y con `srcset` para distintos tamaños.

## Alternativas
- **Redux Toolkit:** más estructura, pero más boilerplate para dos stores pequeños.
- **Vue o Angular:** válidos; se elige React por ecosistema y velocidad de entrega.

## Consecuencias
- Bundle inicial pequeño gracias al lazy loading por ruta.
- Al no manejar el token en JavaScript, un XSS no puede robarlo; aun así se evita `dangerouslySetInnerHTML` y se configura una CSP en nginx.
- shadcn/ui acelera la UI y da accesibilidad (foco, teclado, ARIA) de base, pero añade dependencias (Tailwind, Radix, react-hook-form, zod, sonner) y obliga a revisar el código copiado cuando se actualiza un componente.
- El setup de Vitest necesita polyfills de jsdom para Radix (`ResizeObserver`, `matchMedia`, `hasPointerCapture`, `scrollIntoView`).
- Las pruebas del frontend deben simular la sesión con MSW (respuesta de `/auth/me`), no con un token en el almacenamiento.

# ADR 0003: Autenticación con argon2id y JWT

- **Estado:** Propuesto
- **Fecha:** 2026-10-31

## Contexto
Se requiere registro, login y protección de rutas. Un comentario en el PRD sugiere `hashlib.sha256()` para las contraseñas.

## Decisión
- Hash de contraseñas con **argon2id** (librería `argon2-cffi`, parámetros por defecto), con salt incluido en el hash.
- **JWT de acceso** firmado con HS256, expiración corta configurable (`JWT_EXPIRE_MINUTES`, 60 por defecto), secreto en `JWT_SECRET` por variable de entorno. Claims: `sub` (id de usuario), `role`, `exp`.
- El rol se vuelve a leer de la BD en cada petición protegida para que un cambio de rol o una desactivación apliquen de inmediato.
- Mensajes de login genéricos; comparación de hash en tiempo constante (la hace argon2).
- **Transporte del token: cookie `HttpOnly`.** `POST /auth/login` fija la cookie `access_token` con `HttpOnly`, `Secure` (configurable con `COOKIE_SECURE`, desactivado solo en desarrollo local sin HTTPS), `SameSite=Lax`, `Path=/` y `Max-Age` igual a la expiración del JWT. El cuerpo de la respuesta no incluye el token. `POST /auth/logout` borra la cookie y `GET /auth/me` devuelve el usuario de la sesión actual.
- **Protección CSRF:** `SameSite=Lax` más un middleware que, en métodos que modifican datos (POST, PUT, PATCH, DELETE), rechaza con 403 las peticiones que **traen la cookie de sesión** y cuyo header `Origin` (o `Referer` si falta) no esté en `ALLOWED_ORIGINS`; si no vienen ni `Origin` ni `Referer`, también se rechazan. Las peticiones sin cookie (login, registro) no se restringen, porque no pueden abusar de una sesión.
- **CORS:** con el proxy de nginx (ADR 0007) frontend y API comparten origen. En desarrollo con orígenes distintos se usa `allow_credentials=True` con orígenes explícitos, nunca `*`.

## Alternativas
- **SHA-256 simple (`hashlib`):** rechazado. Es rápido, lo que facilita fuerza bruta y tablas arcoíris, y no es un algoritmo de hash de contraseñas.
- **bcrypt:** válido, pero argon2id es la recomendación actual de OWASP.
- **Token en `localStorage`/`sessionStorage` con header `Authorization`:** rechazado, cualquier XSS puede leerlo.
- **Refresh tokens:** más complejo para el plazo; se deja como mejora futura.

## Consecuencias
- Costo de CPU en login/registro, aceptable y deseado.
- Un token robado sigue siendo válido hasta que expira; se mitiga con expiración corta. No hay revocación del lado del servidor salvo desactivar al usuario.
- El token no es accesible desde JavaScript, lo que reduce el impacto de un XSS, pero obliga a defender CSRF (middleware de `Origin`) y a configurar cookies y CORS con cuidado.
- Los tests del backend y del frontend deben cubrir la cookie, el logout y el rechazo por `Origin` inválido.
- La documentación Swagger debe declarar el esquema de seguridad como `apiKey` en cookie.

## Límite de intentos de login (implementado)
- Se cuentan solo los intentos **fallidos**, por **correo** (5 en 15 min) y por **IP** (20 en 15 min); los valores son configurables (`LOGIN_MAX_FAILURES_PER_EMAIL`, `LOGIN_MAX_FAILURES_PER_IP`, `LOGIN_WINDOW_SECONDS`).
- Al superarlo, `POST /auth/login` responde **429** con `Retry-After` y el cuerpo estándar de error, **incluso si la contraseña es correcta**, y no abre sesión.
- Se limita por correo existan o no las cuentas, para que el bloqueo no revele cuáles existen. Un acierto borra los fallos de esa cuenta; los intentos bloqueados no amplían el bloqueo.
- Contadores en Redis con ventana fija (`INCR` + `EXPIRE` atómicos en Lua). Si Redis no responde, no se bloquea a nadie (falla abierto): es defensa en profundidad, la barrera principal es argon2id.
- **IP real del cliente:** nginx **sobrescribe** `X-Forwarded-For` con `$remote_addr` (no lo concatena) y el backend confía en esa cabecera (`FORWARDED_ALLOW_IPS`); un cliente no puede falsear su origen. El puerto 8000 solo se publica en `127.0.0.1`.
- **Compromiso asumido:** quien conozca el correo de otra persona puede bloquear su acceso durante la ventana (denegación de servicio dirigida). Se acepta a cambio de frenar la fuerza bruta; el desbloqueo es automático al vencer la ventana, sin intervención de nadie.
- **Concurrencia del hashing:** `PASSWORD_HASH_CONCURRENCY` (4 por defecto) limita los hashes argon2 simultáneos (64 MiB cada uno) para que una ráfaga de altas o de logins no agote memoria ni CPU; las peticiones esperan su turno.

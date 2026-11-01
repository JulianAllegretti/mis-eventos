#!/usr/bin/env sh
# Crea .env a partir de .env.example con secretos aleatorios. Nunca sobrescribe un .env existente.
set -eu
cd "$(dirname "$0")/.."

if [ -f .env ]; then
  echo ".env ya existe: no se modifica." >&2
  exit 0
fi
if ! command -v openssl >/dev/null 2>&1; then
  echo "Hace falta openssl para generar los secretos." >&2
  echo "Alternativa: copia .env.example a .env y completa JWT_SECRET, ADMIN_PASSWORD, POSTGRES_PASSWORD y GRAFANA_ADMIN_PASSWORD." >&2
  exit 1
fi

# Solo caracteres alfanuméricos: son seguros dentro de URLs, de sed y de archivos .env.
rand() { openssl rand -base64 64 | tr -dc 'A-Za-z0-9' | cut -c1-"$1"; }

DB_PASSWORD=$(rand 24)
JWT=$(rand 48)
ADMIN_PASSWORD=$(rand 16)
GRAFANA_PASSWORD=$(rand 16)

sed \
  -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$DB_PASSWORD|" \
  -e "s|^DATABASE_URL=.*|DATABASE_URL=postgresql+psycopg://miseventos:$DB_PASSWORD@db:5432/miseventos|" \
  -e "s|^JWT_SECRET=.*|JWT_SECRET=$JWT|" \
  -e "s|^ADMIN_PASSWORD=.*|ADMIN_PASSWORD=$ADMIN_PASSWORD|" \
  -e "s|^GRAFANA_ADMIN_PASSWORD=.*|GRAFANA_ADMIN_PASSWORD=$GRAFANA_PASSWORD|" \
  .env.example > .env
chmod 600 .env

echo "Se creó .env con secretos aleatorios (no se versiona)."
echo "  Administrador de la aplicación: admin@example.com / $ADMIN_PASSWORD"
echo "  Grafana (solo con el perfil observability): admin / $GRAFANA_PASSWORD"

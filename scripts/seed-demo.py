#!/usr/bin/env python3
"""Carga datos de ejemplo usando la API (no toca la base de datos directamente).

Uso:  python3 scripts/seed-demo.py [--base http://localhost:8080] [--admin-password CLAVE]

Crea un organizador, ponentes, eventos con agenda y asistentes inscritos. Solo usa la biblioteca
estándar. Si los datos de ejemplo ya existen, no hace nada. La clave del administrador se toma de
ADMIN_PASSWORD del archivo .env.
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from http.cookiejar import CookieJar
from pathlib import Path

PASSWORD = "demo12345"
ORGANIZER = "organizador@example.com"
ATTENDEES = [f"asistente{i}@example.com" for i in range(1, 7)]
FIRST_EVENT = "Congreso de Python Colombia"


class Api:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    def call(self, method: str, path: str, body: dict | None = None, ok: tuple[int, ...] = (200, 201, 204)):
        request = urllib.request.Request(
            f"{self.base}/api/v1{path}",
            method=method,
            data=json.dumps(body).encode() if body is not None else None,
            # El backend exige un Origin permitido en las escrituras que llevan la cookie de sesión.
            headers={"Content-Type": "application/json", "Origin": self.base},
        )
        try:
            with self.opener.open(request, timeout=60) as response:
                raw = response.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as error:
            if error.code in ok:
                return None
            detail = error.read().decode()[:300]
            sys.exit(f"Error {error.code} en {method} {path}: {detail}")

    def login(self, email: str, password: str) -> None:
        self.call("POST", "/auth/login", {"email": email, "password": password})

    def ensure_user(self, email: str, name: str) -> None:
        # 409 = ya existía: en ese caso solo se inicia sesión.
        self.call("POST", "/auth/register", {"email": email, "password": PASSWORD, "full_name": name}, ok=(409,))
        self.login(email, PASSWORD)


BOGOTA_UTC_OFFSET = 5  # las horas del plan son locales (UTC-5); la API las recibe en UTC


def when(days: float, hour: int = 0) -> str:
    """Instante a `days` días de hoy y a la hora local `hour` (hora de Bogotá), en ISO UTC."""
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return (today + timedelta(days=days, hours=hour + BOGOTA_UTC_OFFSET)).isoformat()


def admin_password(arg: str | None) -> str:
    if arg:
        return arg
    env = Path(__file__).resolve().parent.parent / ".env"
    match = re.search(r"^ADMIN_PASSWORD=(.+)$", env.read_text(), re.M) if env.exists() else None
    if not match:
        sys.exit("No encontré ADMIN_PASSWORD en .env. Pásala con --admin-password.")
    return match.group(1).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", default="http://localhost:8080")
    parser.add_argument("--admin-password")
    args = parser.parse_args()

    admin = Api(args.base)
    admin.login("admin@example.com", admin_password(args.admin_password))
    existing = admin.call("GET", f"/events?q={urllib.parse.quote(FIRST_EVENT)}")
    if existing and existing["total"] > 0:
        print("Los datos de ejemplo ya existen: no se hace nada.")
        return

    print("Creando el organizador…")
    organizer = Api(args.base)
    organizer.ensure_user(ORGANIZER, "Olivia Organizadora")
    me = organizer.call("GET", "/auth/me")
    admin.call("PATCH", f"/admin/users/{me['id']}", {"role": "organizer"})

    print("Creando ponentes…")
    speakers = {
        name: organizer.call("POST", "/speakers", {"name": name, "bio": bio})["id"]
        for name, bio in [
            ("Marta Díaz", "Ingeniera de software e instructora de Python."),
            ("Luis Gómez", "Arquitecto de sistemas, especialista en bases de datos."),
            ("Carla Ruiz", "Ingeniera de plataforma y divulgadora de DevOps."),
        ]
    }

    print("Creando eventos y agendas…")
    plan = [
        (FIRST_EVENT, "Dos días de charlas y talleres sobre el ecosistema Python: web, datos y automatización.",
         "Centro de Convenciones Ágora, Bogotá", 20, 9, 2 * 24 - 15, 120, [
            ("Introducción a FastAPI", "Marta Díaz", 20, 10, 12, 60),
            ("Bases de datos relacionales con SQLModel", "Luis Gómez", 20, 14, 16, 60),
            ("Despliegue con Docker Compose", "Carla Ruiz", 21, 10, 12, 40),
            ("Observabilidad en la práctica", "Carla Ruiz", 21, 14, 16, 40),
        ]),
        ("Taller de Docker para principiantes", "Aprende contenedores desde cero con ejercicios guiados.",
         "Sala 3, Ruta N, Medellín", 9, 14, 6, 6, [("Contenedores desde cero", "Carla Ruiz", 9, 15, 18, 6)]),
        ("Meetup de Datos (cupos agotados)", "Encuentro mensual de la comunidad de datos.",
         "Café Cultural, Cali", 5, 18, 3, 3, []),
        ("Arquitectura hexagonal en la práctica", "Cómo separar el dominio de los frameworks sin morir en el intento.",
         "Auditorio UdeA, Medellín", 14, 15, 3, 60, [("Puertos y adaptadores", "Luis Gómez", 14, 15, 17, 60)]),
    ]
    event_ids = {}
    for name, description, location, day, hour, duration, capacity, sessions in plan:
        event = organizer.call("POST", "/events", {
            "name": name, "description": description, "location": location,
            "start_at": when(day, hour), "end_at": when(day, hour + duration), "capacity": capacity})
        event_ids[name] = event["id"]
        for title, speaker, s_day, s_start, s_end, s_capacity in sessions:
            organizer.call("POST", f"/events/{event['id']}/sessions", {
                "speaker_id": speakers[speaker], "title": title, "start_at": when(s_day, s_start),
                "end_at": when(s_day, s_end), "capacity": min(s_capacity, capacity)})
        organizer.call("POST", f"/events/{event['id']}/publish")

    print("Inscribiendo asistentes…")
    signups = {
        "Taller de Docker para principiantes": ATTENDEES[:5],
        "Meetup de Datos (cupos agotados)": ATTENDEES[:3],
        FIRST_EVENT: ATTENDEES,
        "Arquitectura hexagonal en la práctica": ATTENDEES[:2],
    }
    for index, email in enumerate(ATTENDEES):
        person = Api(args.base)
        person.ensure_user(email, f"Asistente {index + 1}")
        for name, people in signups.items():
            if email in people:
                person.call("POST", f"/events/{event_ids[name]}/registrations")

    print(f"""
Listo. Abre {args.base}

  Administrador:  admin@example.com / (tu ADMIN_PASSWORD del .env)
  Organizador:    {ORGANIZER} / {PASSWORD}
  Asistentes:     asistente1@example.com … asistente6@example.com / {PASSWORD}
""")


if __name__ == "__main__":
    main()

from typing import Protocol


class Metrics(Protocol):
    """Métricas de negocio (ADR 0009). Las llamadas son baratas y nunca bloquean.

    Todas las etiquetas tienen un conjunto cerrado de valores: nunca se usan ids, correos ni
    texto del usuario, para no disparar la cardinalidad.
    """

    def registration_attempt(self, result: str) -> None:
        """result: ok | full | duplicate | rejected | error."""
        ...

    def slot_filter(self, result: str) -> None:
        """result: allowed | rejected | bypassed | duplicate_claim."""
        ...

    def slot_compensation(self) -> None:
        """Se devolvió un cupo a Redis porque PostgreSQL rechazó la inscripción."""
        ...

    def event_closed(self, source: str, count: int = 1) -> None:
        """source: manual | scheduler."""
        ...

    def maintenance_run(self, task: str, ok: bool) -> None:
        """task: finish_expired | reconcile_slots."""
        ...

    def login_attempt(self, result: str) -> None:
        """result: success | invalid | rate_limited."""
        ...

    def cache_lookup(self, kind: str, hit: bool) -> None:
        """kind: event | search."""
        ...

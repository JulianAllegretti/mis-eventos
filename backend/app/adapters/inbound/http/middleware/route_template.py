from starlette.types import Scope

UNMATCHED = "unmatched"


def route_template(scope: Scope) -> str:
    """Plantilla completa de la ruta atendida, p. ej. `/api/v1/events/{event_id}`.

    `route.path` es relativo al router (no incluye el prefijo con el que se montó), así que el
    prefijo se recupera comparando el path real con la ruta concreta. Nunca devuelve la URL con
    valores reales: sirve de etiqueta de métricas y de campo de log sin disparar la cardinalidad.
    """
    route = scope.get("route")
    if route is None:
        return UNMATCHED
    template: str = getattr(route, "path_format", None) or route.path
    params = {key: str(value) for key, value in scope.get("path_params", {}).items()}
    try:
        concrete = template.format(**params)
    except (KeyError, IndexError, ValueError):
        return template
    path: str = scope.get("path", "")
    if concrete and path.endswith(concrete):
        return path[: len(path) - len(concrete)] + template
    return template

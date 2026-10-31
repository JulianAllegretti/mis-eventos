from app.application.dto.queries import MAX_PAGE_SIZE
from app.domain.errors import ValidationFailed


def resolve_page(page: int, page_size: int) -> tuple[int, int, int]:
    """Valida la paginación y devuelve (page, limit, offset)."""
    if page < 1 or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise ValidationFailed(f"page debe ser ≥ 1 y page_size estar entre 1 y {MAX_PAGE_SIZE}")
    return page, page_size, (page - 1) * page_size

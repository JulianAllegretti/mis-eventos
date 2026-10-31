LIKE_ESCAPE = "\\"


def escape_like(text: str) -> str:
    """Escapa los comodines de LIKE para que el texto del usuario se busque literalmente.

    El valor sigue viajando como parámetro ligado; esto solo neutraliza % y _.
    """
    return (
        text.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2)
        .replace("%", f"{LIKE_ESCAPE}%")
        .replace("_", f"{LIKE_ESCAPE}_")
    )


def contains_pattern(text: str) -> str:
    return f"%{escape_like(text)}%"

from fastapi import Response

SESSION_COOKIE_NAME = "access_token"


def set_session_cookie(response: Response, token: str, max_age: int, secure: bool) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=max_age,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response, secure: bool) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME, path="/", httponly=True, secure=secure, samesite="lax"
    )

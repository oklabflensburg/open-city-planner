from contextvars import ContextVar, Token

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
route_var: ContextVar[str | None] = ContextVar("route", default=None)


def bind_request_context(request_id: str) -> tuple[Token[str | None], Token[str | None]]:
    return request_id_var.set(request_id), route_var.set(None)


def clear_request_context(tokens: tuple[Token[str | None], Token[str | None]]) -> None:
    request_id_var.reset(tokens[0])
    route_var.reset(tokens[1])


def request_id() -> str | None:
    return request_id_var.get()


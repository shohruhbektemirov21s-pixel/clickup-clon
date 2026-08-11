"""Small view-layer helpers shared by every app."""

from typing import Any

from rest_framework.request import Request
from rest_framework.response import Response

from config.pagination import StandardPagination


def client_id_of(request: Request) -> str | None:
    return request.headers.get("X-Client-Id") or None


def paginate(
    request: Request,
    items: Any,
    serializer_class: Any,
    context: dict[str, Any] | None = None,
    **serializer_kwargs: Any,
) -> Response:
    paginator = StandardPagination()
    page: list[Any] | None = paginator.paginate_queryset(items, request)
    serializer = serializer_class(
        page, many=True, context=context or {"request": request}, **serializer_kwargs
    )
    return paginator.get_paginated_response(serializer.data)


def parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).lower() in ("1", "true", "yes")

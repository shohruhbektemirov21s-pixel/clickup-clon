"""Small view-layer helpers shared by every app."""

from config.pagination import StandardPagination


def client_id_of(request):
    return request.headers.get("X-Client-Id") or None


def paginate(request, items, serializer_class, context=None, **serializer_kwargs):
    paginator = StandardPagination()
    page = paginator.paginate_queryset(items, request)
    serializer = serializer_class(
        page, many=True, context=context or {"request": request}, **serializer_kwargs
    )
    return paginator.get_paginated_response(serializer.data)


def parse_bool(value, default=False):
    if value is None:
        return default
    return str(value).lower() in ("1", "true", "yes")

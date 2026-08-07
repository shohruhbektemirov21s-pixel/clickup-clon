"""A single, predictable error envelope for the whole API.

Every failing request answers with:

    {"error": {"code": "validation_error", "message": "...", "details": {...}}}

so the frontend has exactly one shape to parse. See docs/API_CONTRACT.md.
"""

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

CODES = {
    400: "bad_request",
    401: "authentication_failed",
    403: "permission_denied",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    415: "unsupported_media_type",
    429: "throttled",
    500: "server_error",
}


def _has_token_not_valid(detail):
    """simplejwt marks expired/blacklisted/invalid JWTs with code 'token_not_valid'."""
    if isinstance(detail, exceptions.ErrorDetail):
        return detail.code == "token_not_valid"
    if isinstance(detail, dict):
        return any(_has_token_not_valid(v) for v in detail.values())
    if isinstance(detail, list):
        return any(_has_token_not_valid(v) for v in detail)
    return False


def _code_for(exc, status_code):
    api_code = getattr(exc, "api_code", None)
    if api_code:
        return api_code
    if isinstance(exc, (InvalidToken, TokenError)):
        return "token_not_valid"
    if isinstance(exc, exceptions.ValidationError):
        return "validation_error"
    if status_code == 401 and _has_token_not_valid(getattr(exc, "detail", None)):
        return "token_not_valid"
    return CODES.get(status_code, "error")


def _message_for(exc, data):
    detail = getattr(exc, "detail", None)
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list) and detail:
        return str(detail[0])
    if isinstance(data, dict):
        return "Request payload is invalid."
    return str(data)


def api_exception_handler(exc, context):
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()

    response = drf_exception_handler(exc, context)
    if response is None:
        # Unhandled exception: let Django's own 500 handling deal with it so
        # DEBUG tracebacks and error reporting still work.
        return None

    data = response.data
    custom_details = getattr(exc, "details", None)
    if custom_details:
        details = custom_details
    else:
        details = data if isinstance(data, dict) else {"detail": data}

    response.data = {
        "error": {
            "code": _code_for(exc, response.status_code),
            "message": _message_for(exc, data),
            "details": details,
        }
    }
    return response


def error_response(status_code, code, message, details=None):
    """Build the same envelope from view code without raising."""
    return Response(
        {"error": {"code": code, "message": message, "details": details or {}}},
        status=status_code,
    )

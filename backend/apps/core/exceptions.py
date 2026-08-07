"""API exceptions carrying the contract's closed error-code vocabulary."""

from rest_framework import status
from rest_framework.exceptions import APIException


class ApiError(APIException):
    """An exception whose ``api_code`` flows straight into the error envelope."""

    status_code = status.HTTP_400_BAD_REQUEST
    api_code = "bad_request"

    def __init__(self, message=None, details=None, code=None, status_code=None):
        if code is not None:
            self.api_code = code
        if status_code is not None:
            self.status_code = status_code
        self.details = details or {}
        detail = message or self.default_detail
        super().__init__(detail=detail)


class Conflict(ApiError):
    status_code = status.HTTP_409_CONFLICT
    api_code = "conflict"
    default_detail = "The request conflicts with the current state."


class PositionConflict(Conflict):
    api_code = "position_conflict"
    default_detail = "Neighbours are stale; refetch the column and retry."


class InvalidStatusForList(ApiError):
    status_code = status.HTTP_400_BAD_REQUEST
    api_code = "invalid_status_for_list"
    default_detail = "Status does not belong to this list's effective status set."

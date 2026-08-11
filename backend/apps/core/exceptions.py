"""API exceptions carrying the contract's closed error-code vocabulary."""

from typing import Any

from rest_framework import status
from rest_framework.exceptions import APIException


class ApiError(APIException):
    """An exception whose ``api_code`` flows straight into the error envelope."""

    # `int` ATAYLAB: quyidagi sinflar (Conflict va h.k.) buni boshqa kodga
    # almashtiradi, `Literal[400]` esa ularni tip xatosiga aylantirardi.
    status_code: int = status.HTTP_400_BAD_REQUEST
    api_code = "bad_request"

    def __init__(
        self,
        message: str | None = None,
        details: dict[str, Any] | None = None,
        code: str | None = None,
        status_code: int | None = None,
    ) -> None:
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


# `InvalidStatusForList` (`invalid_status_for_list`) OLIB TASHLANDI: status
# endi ro'yxatga bog'liq emas (`apps.core.enums.TaskStatus` — yopiq kod
# to'plami), ya'ni "bu status shu ro'yxatga tegishli emas" holati mavjud
# emas. Noma'lum kod oddiy `validation_error` (400) beradi.

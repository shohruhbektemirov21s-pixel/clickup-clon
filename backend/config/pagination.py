from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """Page-number pagination, as documented in docs/API_CONTRACT.md.

    page_size > 100 (or non-numeric / < 1) is a 400 validation_error, not a
    silent clamp (contract section 1.5).
    """

    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_page_size(self, request):
        raw = request.query_params.get(self.page_size_query_param)
        if raw is None:
            return self.page_size
        try:
            value = int(raw)
        except (TypeError, ValueError):
            raise ValidationError({"page_size": ["page_size must be an integer."]})
        if value < 1 or value > self.max_page_size:
            raise ValidationError(
                {"page_size": [f"page_size must be between 1 and {self.max_page_size}."]}
            )
        return value

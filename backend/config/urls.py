from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return Response({"status": "ok"})


api_v1 = [
    path("health/", health, name="health"),
    path("", include("apps.core.urls")),
    path("", include("apps.accounts.urls")),
    path("", include("apps.workspaces.urls")),
    path("", include("apps.tasks.urls")),
    path("", include("apps.comments.urls")),
    path("", include("apps.emailcheck.urls")),
    path("", include("apps.chat.urls")),
    path("", include("apps.notifications.urls")),
]

urlpatterns = [
    # Path is configurable (ADMIN_URL) so the admin is not sitting on the
    # default location every scanner probes first.
    path(settings.ADMIN_URL, admin.site.urls),
    path("api/v1/", include((api_v1, "v1"))),
]

# The OpenAPI schema is a complete map of the API. Only register the routes when
# they are actually wanted; SPECTACULAR_SETTINGS["SERVE_PERMISSIONS"] restricts
# them to staff on top of that.
if settings.DEBUG or settings.EXPOSE_API_DOCS:
    from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

    urlpatterns += [
        path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
        path(
            "api/docs/",
            SpectacularSwaggerView.as_view(url_name="schema"),
            name="swagger-ui",
        ),
    ]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

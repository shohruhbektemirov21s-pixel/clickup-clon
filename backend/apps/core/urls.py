from django.urls import path

from apps.core import showcase

urlpatterns = [
    # Anonim o'qish uchun yagona endpoint — landing sahifasi shundan oziqlanadi.
    path("public/showcase/", showcase.showcase, name="public-showcase"),
]

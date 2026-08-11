from django.urls import path

from apps.notifications import views

urlpatterns = [
    path("notifications/", views.NotificationListView.as_view(), name="notification-list"),
    # `unread-count/` va `read-all/` `<uuid:…>` dan OLDIN kelishi shart emas
    # (UUID converter matnli segmentga mos kelmaydi), lekin tartib baribir
    # o'qishga qulay bo'lgani uchun shunday qoldirilgan.
    path(
        "notifications/unread-count/",
        views.NotificationUnreadCountView.as_view(),
        name="notification-unread-count",
    ),
    path(
        "notifications/read-all/",
        views.NotificationReadAllView.as_view(),
        name="notification-read-all",
    ),
    path(
        "notifications/<uuid:notification_id>/read/",
        views.NotificationReadView.as_view(),
        name="notification-read",
    ),
]

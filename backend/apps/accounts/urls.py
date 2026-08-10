from django.urls import path

from apps.accounts import views

urlpatterns = [
    path("auth/register/", views.RegisterView.as_view(), name="auth-register"),
    path("auth/login/", views.LoginView.as_view(), name="auth-login"),
    path("auth/demo/", views.DemoLoginView.as_view(), name="auth-demo"),
    path("auth/refresh/", views.RefreshView.as_view(), name="auth-refresh"),
    path("auth/logout/", views.LogoutView.as_view(), name="auth-logout"),
    path("auth/password/change/", views.PasswordChangeView.as_view(), name="auth-password-change"),
    # WebSocket handshake chiptasi (§15.1) — `?token=` o'rniga (AppSec O-3).
    path("realtime/ticket/", views.RealtimeTicketView.as_view(), name="realtime-ticket"),
    path("me/", views.MeView.as_view(), name="me"),
    path("me/avatar/", views.MeAvatarView.as_view(), name="me-avatar"),
]

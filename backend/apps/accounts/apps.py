from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"

    def ready(self):
        # Autentifikatsiya audit signallari (AppSec B.2.4). `ready()` — yagona
        # ishonchli joy: import qilinmasa receiver'lar ro'yxatdan o'tmaydi va
        # jurnal jimgina bo'sh qoladi.
        from apps.accounts import signals  # noqa: F401

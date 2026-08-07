from django.apps import AppConfig
from django.db.backends.signals import connection_created


def _register_sqlite_c_collation(sender, connection, **kwargs):
    """position columns are declared db_collation="C" (byte order) for PostgreSQL.

    SQLite has no built-in "C" collation, so register one that compares by
    code point — identical to BINARY for the ASCII base-62 alphabet we use.
    """
    if connection.vendor == "sqlite":
        connection.connection.create_collation("C", lambda a, b: (a > b) - (a < b))


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"

    def ready(self):
        connection_created.connect(_register_sqlite_c_collation)
        # Cover connections opened before this signal was connected.
        from django.db import connections

        for conn in connections.all(initialized_only=True):
            if conn.vendor == "sqlite" and conn.connection is not None:
                conn.connection.create_collation("C", lambda a, b: (a > b) - (a < b))

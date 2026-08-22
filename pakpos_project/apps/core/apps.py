from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pakpos_project.apps.core'

    def ready(self):
        import os
        import sys
        from django.db.backends.signals import connection_created

        # Configure SQLite for high concurrency (WAL Mode & Busy Timeout)
        def configure_sqlite(sender, connection, **kwargs):
            if connection.vendor == 'sqlite':
                cursor = connection.cursor()
                cursor.execute('PRAGMA journal_mode = WAL;')
                cursor.execute('PRAGMA synchronous = NORMAL;')
                cursor.execute('PRAGMA busy_timeout = 30000;')

        connection_created.connect(configure_sqlite)

        # Register Auto-Delete Sync Signals for Google Sheets
        try:
            from pakpos_project.apps.core.signals import register_delete_signals
            register_delete_signals()
        except Exception:
            pass

        # Avoid running worker during migrations or management commands
        if 'runserver' in sys.argv or 'gunicorn' in ''.join(sys.argv) or 'uwsgi' in ''.join(sys.argv):
            # In development, runserver starts two processes (one for auto-reload)
            # RUN_MAIN is true only in the reloaded process.
            if os.environ.get('RUN_MAIN') == 'true' or 'runserver' not in sys.argv:
                from pakpos_project.apps.core.sync_worker import start_sync_worker
                from pakpos_project.apps.core.payment_alert_worker import start_payment_alert_worker
                start_sync_worker()
                start_payment_alert_worker()


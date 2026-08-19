from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pakpos_project.apps.core'

    def ready(self):
        import os
        import sys
        
        # Avoid running worker during migrations or management commands
        if 'runserver' in sys.argv or 'gunicorn' in ''.join(sys.argv) or 'uwsgi' in ''.join(sys.argv):
            # In development, runserver starts two processes (one for auto-reload)
            # RUN_MAIN is true only in the reloaded process.
            if os.environ.get('RUN_MAIN') == 'true' or 'runserver' not in sys.argv:
                from pakpos_project.apps.core.sync_worker import start_sync_worker
                start_sync_worker()

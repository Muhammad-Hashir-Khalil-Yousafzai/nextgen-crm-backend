# usermanage/apps.py
from django.apps import AppConfig


class UsermanageConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'crmapp.system.usermanage'
    verbose_name       = 'User Management'

    def ready(self):
        import crmapp.system.usermanage.signals  # noqa
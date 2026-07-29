# roles/apps.py
from django.apps import AppConfig

class RolesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'crmapp.system.roles'
    verbose_name       = 'Roles & Permissions'

    def ready(self):
        import crmapp.system.roles.signals  # noqa
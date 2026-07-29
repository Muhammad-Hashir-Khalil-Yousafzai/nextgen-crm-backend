# auth_security/apps.py
from django.apps import AppConfig

class AuthSecurityConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'crmapp.system.auth_security'
    verbose_name       = 'Auth & Security'

    def ready(self):
        import crmapp.system.auth_security.signals  # noqa
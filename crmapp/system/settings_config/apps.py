# settings_config/apps.py
from django.apps import AppConfig

class SettingsConfigApp(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'crmapp.system.settings_config'
    verbose_name       = 'System Settings'
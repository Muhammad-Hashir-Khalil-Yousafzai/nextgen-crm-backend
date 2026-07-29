from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "crmapp.agentic.core"
    label = "agentic_core"
    verbose_name = "Agentic Core"
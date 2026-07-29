from django.apps import AppConfig


class XAIConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "crmapp.ai.xai"
    label = "ai_xai"
    verbose_name = "Explainable AI"

    def ready(self):
        pass  # signals can be registered here later

from django.apps import AppConfig


class RecommendationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name               = "crmapp.ai.recommendation"
    label              = "ai_recommendation"
    verbose_name       = "AI Recommendation Engine"
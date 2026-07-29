from django.apps import AppConfig

class EmotionDetectionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "crmapp.ai.emotion_detection"
    label = "emotion_detection"

    def ready(self):
        pass  # no local model to preload — using HuggingFace API
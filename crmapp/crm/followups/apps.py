from django.apps import AppConfig


class FollowUpsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name  = 'crmapp.crm.followups'
    label = 'crm_followups'

    def ready(self):
        # Signal register karne ke liye import zaroori hai
        import crmapp.crm.followups.signals  # noqa: F401
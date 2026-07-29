from django.apps import AppConfig


class DealsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name  = 'crmapp.crm.deals'
    label = 'crm_deals'

    def ready(self):
        import crmapp.crm.deals.signals  # noqa
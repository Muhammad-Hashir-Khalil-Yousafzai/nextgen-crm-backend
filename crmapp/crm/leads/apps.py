from django.apps import AppConfig


class LeadsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name  = 'crmapp.crm.leads'
    label = 'crm_leads'

    def ready(self):
        """
        Django start hote hi signals register ho jaate hain.
        Yeh line ZAROOR honi chahiye — warna automation kaam nahi karega.
        """
        import crmapp.crm.leads.signals  # noqa: F401
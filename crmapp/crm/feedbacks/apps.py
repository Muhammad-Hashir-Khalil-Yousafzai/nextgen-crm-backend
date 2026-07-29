from django.apps import AppConfig

class CrmFeedbackConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'crmapp.crm.feedbacks'
    label = 'crm_feedback'
    verbose_name = 'CRM Feedback'
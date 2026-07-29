# crm_contracts/apps.py
from django.apps import AppConfig


class CrmContractsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'crmapp.crm.contracts'
    label = 'crm_contracts'
    verbose_name = 'CRM Contracts'
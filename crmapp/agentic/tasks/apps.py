# crmapp/agentic/tasks/apps.py
from django.apps import AppConfig

class TasksConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'crmapp.agentic.tasks'
    label = 'agentic_tasks'
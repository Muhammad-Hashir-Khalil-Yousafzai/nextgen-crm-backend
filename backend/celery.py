"""
backend/celery.py

Celery application config.
Place this file in the same folder as settings.py (the backend/ folder).

Start the worker with:
    celery -A backend worker --loglevel=info --pool=solo

Start the beat scheduler (for periodic tasks) with:
    celery -A backend beat --loglevel=info
"""

import os
from celery import Celery
from celery.signals import worker_ready


# Tell Celery which Django settings to use
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

app = Celery("backend")

# Load config from Django settings, using CELERY_ prefix
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks.py in all installed apps
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")

    
@worker_ready.connect
def reset_agent_statuses(sender, **kwargs):
    import django
    django.setup()
    from crmapp.agentic.core.models import Resource
    Resource.objects.filter(status="busy").update(status="idle")
    print("[Celery] Reset busy agents to idle on worker start")
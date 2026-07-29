# agentic/agents/apps.py
from django.apps import AppConfig


class AgentsConfig(AppConfig):
    name = "crmapp.agentic.agents"
    label = "agentic_agents"

    def ready(self):
        from crmapp.agentic.agents.signals import connect_signals
        connect_signals()
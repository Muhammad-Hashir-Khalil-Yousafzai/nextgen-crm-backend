"""
crmapp/agentic/agents/urls.py

All routes at /api/agentic/agents/
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ResourceViewSet,
    HistoryViewSet,
    AlertsViewSet,
    PerformanceViewSet,
)

router = DefaultRouter()
router.register(r"resources",   ResourceViewSet,   basename="agent-resources")
router.register(r"history",     HistoryViewSet,    basename="agent-history")
router.register(r"alerts",      AlertsViewSet,     basename="agent-alerts")
router.register(r"performance", PerformanceViewSet, basename="agent-performance")

urlpatterns = [
    path("", include(router.urls)),
]
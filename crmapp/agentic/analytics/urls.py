"""
crmapp/agentic/analytics/urls.py

All routes at /api/agentic/analytics/
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    OverviewViewSet,
    AgentAnalyticsViewSet,
    KPIViewSet,
    CompareViewSet,
    HITLViewSet,
    WeeklyTaskViewSet,
    StatsSyncViewSet,
)

router = DefaultRouter()
router.register(r"overview",  OverviewViewSet,       basename="analytics-overview")
router.register(r"agents",    AgentAnalyticsViewSet, basename="analytics-agents")
router.register(r"kpis",      KPIViewSet,            basename="analytics-kpis")
router.register(r"compare",   CompareViewSet,        basename="analytics-compare")
router.register(r"hitl",      HITLViewSet,           basename="analytics-hitl")
router.register(r"weekly",    WeeklyTaskViewSet,     basename="analytics-weekly")
router.register(r"stats",     StatsSyncViewSet,      basename="analytics-stats")

urlpatterns = [
    path("", include(router.urls)),
]

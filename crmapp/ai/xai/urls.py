"""
crmapp/xai/urls.py

All routes at /api/xai/
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    MLModelViewSet,
    PredictionViewSet,
    BiasViewSet,
    AuditLogViewSet,
    ModelIssueViewSet,
    GlobalImportanceViewSet,
    DashboardViewSet,
)

router = DefaultRouter()
router.register(r"models",            MLModelViewSet,           basename="xai-models")
router.register(r"predictions",       PredictionViewSet,        basename="xai-predictions")
router.register(r"bias",              BiasViewSet,              basename="xai-bias")
router.register(r"audit_log",         AuditLogViewSet,          basename="xai-audit-log")
router.register(r"issues",            ModelIssueViewSet,        basename="xai-issues")
router.register(r"global_importance", GlobalImportanceViewSet,  basename="xai-global-importance")
router.register(r"dashboard",         DashboardViewSet,         basename="xai-dashboard")

urlpatterns = [
    path("", include(router.urls)),
]

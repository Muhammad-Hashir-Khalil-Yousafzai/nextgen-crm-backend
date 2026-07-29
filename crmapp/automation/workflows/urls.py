"""
crmapp/workflows/urls.py
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import WorkflowViewSet, ExecutionViewSet, WebhookReceiverView

router = DefaultRouter()
router.register(r"workflows",  WorkflowViewSet,  basename="workflow")
router.register(r"executions", ExecutionViewSet, basename="execution")

urlpatterns = [
    path("", include(router.urls)),
    # Webhook receiver — external systems POST here
    path("webhooks/<str:secret>/", WebhookReceiverView.as_view(), name="workflow-webhook"),
]

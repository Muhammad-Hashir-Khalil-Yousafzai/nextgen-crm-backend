# audit/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AuditLogViewSet

router = DefaultRouter()
router.register(r'logs', AuditLogViewSet, basename='audit-logs')

urlpatterns = [path('', include(router.urls))]

# Registered endpoints:
# GET  /api/system/audit/logs/          → list  (paginated, merged)
# GET  /api/system/audit/logs/{id}/     → retrieve single log
# GET  /api/system/audit/logs/stats/    → today severity counts
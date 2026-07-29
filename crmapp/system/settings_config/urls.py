# settings_config/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SystemSettingView, NotificationSettingView,
    EmailConfigView, test_email_config,
    IntegrationKeyViewSet, BackupRecordViewSet,
)

router = DefaultRouter()
router.register(r'integrations', IntegrationKeyViewSet, basename='integrations')
router.register(r'backups',      BackupRecordViewSet,   basename='backups')

urlpatterns = [
    path('general/',       SystemSettingView.as_view(),       name='system-setting'),
    path('notifications/', NotificationSettingView.as_view(), name='notification-setting'),
    path('email/',         EmailConfigView.as_view(),         name='email-config'),
    path('email/test/',    test_email_config,                 name='email-test'),
    path('',               include(router.urls)),
]
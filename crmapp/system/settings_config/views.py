# settings_config/views.py
from rest_framework import status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from rest_framework.views import APIView

from .models import SystemSetting, NotificationSetting, EmailConfig, IntegrationKey, BackupRecord
from .serializers import (
    SystemSettingSerializer, NotificationSettingSerializer,
    EmailConfigSerializer, EmailConfigWriteSerializer,
    IntegrationKeySerializer, IntegrationKeyWriteSerializer,
    BackupRecordSerializer,
)
from . import services
from crmapp.system.roles.permissions import can


class SystemSettingView(APIView):
    """GET/PATCH /api/settings/general/"""
    def get_permissions(self):
        return [can('settings', 'view')() if self.request.method == 'GET'
                else can('settings', 'edit')()]

    def get(self, request):
        return Response(SystemSettingSerializer(services.get_system_setting()).data)

    def patch(self, request):
        s = SystemSettingSerializer(services.get_system_setting(),
                                    data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        updated = services.update_system_setting(s.validated_data, actor=request.user)
        return Response(SystemSettingSerializer(updated).data)


class NotificationSettingView(APIView):
    """GET/PATCH /api/settings/notifications/"""
    def get_permissions(self):
        return [can('settings', 'view')() if self.request.method == 'GET'
                else can('settings', 'edit')()]

    def get(self, request):
        return Response(NotificationSettingSerializer(services.get_notification_setting()).data)

    def patch(self, request):
        s = NotificationSettingSerializer(services.get_notification_setting(),
                                          data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        updated = services.update_notification_setting(s.validated_data, actor=request.user)
        return Response(NotificationSettingSerializer(updated).data)


class EmailConfigView(APIView):
    """GET/PATCH /api/settings/email/"""
    def get_permissions(self):
        return [can('settings', 'view')() if self.request.method == 'GET'
                else can('settings', 'edit')()]

    def get(self, request):
        return Response(EmailConfigSerializer(services.get_email_config()).data)

    def patch(self, request):
        s = EmailConfigWriteSerializer(services.get_email_config(),
                                       data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        updated = services.update_email_config(s.validated_data, actor=request.user)
        return Response(EmailConfigSerializer(updated).data)


@api_view(['POST'])
@permission_classes([can('settings', 'edit')])
def test_email_config(request):
    """POST /api/settings/email/test/"""
    success = services.test_email_config()
    if success:
        return Response({'detail': 'SMTP connection successful.'})
    return Response({'detail': 'SMTP connection failed.'}, status=status.HTTP_400_BAD_REQUEST)


class IntegrationKeyViewSet(ModelViewSet):
    """GET/POST/PATCH/DELETE /api/settings/integrations/"""
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [can('settings', 'view')()]
        return [can('settings', 'edit')()]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return IntegrationKeyWriteSerializer
        return IntegrationKeySerializer

    def get_queryset(self):
        return services.get_integration_keys()

    def create(self, request, *args, **kwargs):
        s = IntegrationKeyWriteSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        key = services.create_integration_key(s.validated_data, actor=request.user)
        return Response(IntegrationKeySerializer(key).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        key = self.get_object()
        s   = IntegrationKeyWriteSerializer(key, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        updated = services.update_integration_key(key, s.validated_data, actor=request.user)
        return Response(IntegrationKeySerializer(updated).data)

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        key = self.get_object()
        services.delete_integration_key(key, actor=request.user)
        return Response({'detail': 'Integration key deleted.'})


class BackupRecordViewSet(ReadOnlyModelViewSet):
    """GET /api/settings/backups/   POST /api/settings/backups/run/"""
    serializer_class   = BackupRecordSerializer
    permission_classes = [can('settings', 'view')]

    def get_queryset(self):
        return services.get_backup_records()

    @action(detail=False, methods=['post'], url_path='run',
            permission_classes=[can('settings', 'edit')])
    def run_backup(self, request):
        record = services.run_manual_backup(actor=request.user)
        return Response(BackupRecordSerializer(record).data, status=status.HTTP_201_CREATED)
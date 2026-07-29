# settings_config/serializers.py
from rest_framework import serializers
from .models import SystemSetting, NotificationSetting, EmailConfig, IntegrationKey, BackupRecord


class SystemSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SystemSetting
        fields = [
            'id', 'system_name', 'company_name', 'timezone',
            'language', 'date_format', 'currency', 'fiscal_year',
            'primary_color', 'theme', 'logo_url', 'favicon_url',
            'module_config', 'feature_flags', 'updated_at',
        ]
        read_only_fields = ['id', 'updated_at']


class NotificationSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model  = NotificationSetting
        fields = [
            'id',
            'email_notif', 'sms_notif', 'push_notif', 'in_app_notif',
            'new_lead', 'task_assigned', 'deal_closed',
            'invoice_due', 'invoice_paid', 'login_alert',
            'new_contact', 'report_ready', 'system_error',
            'maintenance', 'weekly_report', 'monthly_report',
            'updated_at',
        ]
        read_only_fields = ['id', 'updated_at']


class EmailConfigSerializer(serializers.ModelSerializer):
    """Read — never returns smtp_password."""
    class Meta:
        model  = EmailConfig
        fields = [
            'id', 'smtp_host', 'smtp_port', 'smtp_user',
            'encryption', 'sender_name', 'sender_email',
            'reply_to', 'is_verified', 'updated_at',
        ]
        read_only_fields = ['id', 'is_verified', 'updated_at']


class EmailConfigWriteSerializer(serializers.ModelSerializer):
    """Write — accepts smtp_password (write_only)."""
    class Meta:
        model  = EmailConfig
        fields = [
            'smtp_host', 'smtp_port', 'smtp_user', 'smtp_password',
            'encryption', 'sender_name', 'sender_email', 'reply_to',
        ]
        extra_kwargs = {'smtp_password': {'write_only': True}}


class IntegrationKeySerializer(serializers.ModelSerializer):
    """Read — never returns key_encrypted."""
    class Meta:
        model  = IntegrationKey
        fields = [
            'id', 'name', 'icon_label', 'color_hex',
            'status', 'call_count', 'last_used_at', 'created_at',
        ]
        read_only_fields = ['id', 'call_count', 'last_used_at', 'created_at']


class IntegrationKeyWriteSerializer(serializers.ModelSerializer):
    """Write — accepts key_encrypted (write_only)."""
    class Meta:
        model  = IntegrationKey
        fields = ['name', 'icon_label', 'color_hex', 'key_encrypted', 'status']
        extra_kwargs = {'key_encrypted': {'write_only': True}}


class BackupRecordSerializer(serializers.ModelSerializer):
    initiated_by_name = serializers.SerializerMethodField()

    class Meta:
        model  = BackupRecord
        fields = [
            'id', 'name', 'size_display', 'backup_type',
            'status', 'file_path', 'error_msg',
            'initiated_by', 'initiated_by_name',
            'created_at', 'completed_at',
        ]
        read_only_fields = ['id', 'created_at', 'completed_at', 'status']

    def get_initiated_by_name(self, obj):
        if not obj.initiated_by: return None
        p = getattr(obj.initiated_by, 'profile', None)
        return p.full_name if p else obj.initiated_by.email
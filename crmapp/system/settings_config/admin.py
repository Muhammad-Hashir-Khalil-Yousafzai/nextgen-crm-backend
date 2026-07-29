# settings_config/admin.py
from django.contrib import admin
from .models import SystemSetting, NotificationSetting, EmailConfig, IntegrationKey, BackupRecord


@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display    = ['system_name', 'company_name', 'theme', 'language', 'updated_at']
    readonly_fields = ['updated_at', 'updated_by']

    def has_add_permission(self, request):
        return not SystemSetting.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(NotificationSetting)
class NotificationSettingAdmin(admin.ModelAdmin):
    list_display    = ['email_notif', 'sms_notif', 'push_notif', 'updated_at']
    readonly_fields = ['updated_at']

    def has_add_permission(self, request):
        return not NotificationSetting.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EmailConfig)
class EmailConfigAdmin(admin.ModelAdmin):
    list_display    = ['smtp_host', 'smtp_port', 'smtp_user', 'encryption', 'is_verified']
    readonly_fields = ['is_verified', 'updated_at']

    def has_add_permission(self, request):
        return not EmailConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(IntegrationKey)
class IntegrationKeyAdmin(admin.ModelAdmin):
    list_display    = ['name', 'status', 'call_count', 'last_used_at', 'created_at']
    list_filter     = ['status']
    search_fields   = ['name']
    readonly_fields = ['call_count', 'last_used_at', 'created_at']


@admin.register(BackupRecord)
class BackupRecordAdmin(admin.ModelAdmin):
    list_display    = ['name', 'backup_type', 'status', 'size_display', 'initiated_by', 'created_at']
    list_filter     = ['backup_type', 'status']
    readonly_fields = ['created_at', 'completed_at']

    def has_add_permission(self, request): return False
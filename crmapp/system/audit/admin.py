# audit/admin.py
from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display    = ['timestamp', 'user', 'action', 'module', 'entity', 'severity', 'ip_address']
    list_filter     = ['action', 'module', 'severity']
    search_fields   = ['entity', 'ip_address', 'user__email', 'user__profile__full_name']
    readonly_fields = [f.name for f in AuditLog._meta.fields]
    ordering        = ['-timestamp']

    def has_add_permission(self, request):               return False
    def has_change_permission(self, request, obj=None):  return False
    def has_delete_permission(self, request, obj=None):  return False
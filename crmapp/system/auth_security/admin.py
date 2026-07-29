# auth_security/admin.py
from django.contrib import admin
from .models import LoginLog, MFAUser, APIToken, SSOProvider, SecurityPolicy, BlockedIP


@admin.register(LoginLog)
class LoginLogAdmin(admin.ModelAdmin):
    list_display    = ['email_attempted', 'status', 'ip_address', 'city', 'mfa_used', 'timestamp']
    list_filter     = ['status', 'mfa_used']
    search_fields   = ['email_attempted', 'ip_address', 'city']
    readonly_fields = [f.name for f in LoginLog._meta.fields]

    def has_add_permission(self, request):               return False
    def has_change_permission(self, request, obj=None):  return False


@admin.register(MFAUser)
class MFAUserAdmin(admin.ModelAdmin):
    list_display    = ['user', 'mfa_enabled', 'method', 'backup_codes_remaining', 'last_verified']
    list_filter     = ['mfa_enabled', 'method']
    search_fields   = ['user__email', 'user__profile__full_name']
    readonly_fields = ['last_verified']

    def backup_codes_remaining(self, obj): return len(obj.backup_codes)
    backup_codes_remaining.short_description = 'Backup Codes Left'


@admin.register(APIToken)
class APITokenAdmin(admin.ModelAdmin):
    list_display    = ['name', 'token_prefix', 'status', 'call_count', 'expires_at']
    list_filter     = ['status']
    search_fields   = ['name']
    readonly_fields = ['token_hash', 'token_prefix', 'call_count', 'created_at', 'last_used_at']

    def has_add_permission(self, request): return False


@admin.register(SSOProvider)
class SSOProviderAdmin(admin.ModelAdmin):
    list_display  = ['name', 'protocol', 'is_enabled', 'user_count']
    list_filter   = ['protocol', 'is_enabled']
    search_fields = ['name']


@admin.register(SecurityPolicy)
class SecurityPolicyAdmin(admin.ModelAdmin):
    list_display    = ['max_attempts', 'lockout_duration', 'session_timeout', 'require_mfa', 'updated_at']
    readonly_fields = ['updated_at']

    def has_add_permission(self, request):
        return not SecurityPolicy.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(BlockedIP)
class BlockedIPAdmin(admin.ModelAdmin):
    list_display    = ['ip_address', 'reason', 'city', 'blocked_by', 'blocked_at', 'is_active']
    list_filter     = ['is_active']
    search_fields   = ['ip_address', 'reason']
    readonly_fields = ['blocked_at']
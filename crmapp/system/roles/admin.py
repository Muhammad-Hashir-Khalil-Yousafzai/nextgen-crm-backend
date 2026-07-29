# roles/admin.py
from django.contrib import admin
from .models import Role, Permission, RolePermission, UserRole, TemporaryAccess


class RolePermissionInline(admin.TabularInline):
    model  = RolePermission
    extra  = 0
    fields = ['permission', 'granted']


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display    = ['name', 'slug', 'level', 'is_system', 'user_count', 'created_at']
    list_filter     = ['is_system', 'level']
    search_fields   = ['name', 'slug']
    readonly_fields = ['slug', 'created_at', 'updated_at']
    inlines         = [RolePermissionInline]

    def user_count(self, obj): return obj.user_count
    user_count.short_description = 'Users'


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ['module', 'action']
    list_filter  = ['module', 'action']
    def has_add_permission(self, request): return False


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display    = ['user', 'role', 'assigned_by', 'assigned_at', 'is_active']
    list_filter     = ['is_active', 'role']
    search_fields   = ['user__email', 'user__profile__full_name', 'role__name']
    readonly_fields = ['assigned_at']


@admin.register(TemporaryAccess)
class TemporaryAccessAdmin(admin.ModelAdmin):
    list_display    = ['user', 'role', 'reason', 'granted_at', 'expires_at', 'is_active']
    list_filter     = ['is_active', 'role']
    readonly_fields = ['granted_at']
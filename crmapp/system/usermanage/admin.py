# usermanage/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User as AuthUser
from .models import UserProfile, Department, UserSession, UserActivityLog


class UserProfileInline(admin.StackedInline):
    model           = UserProfile
    can_delete      = False
    verbose_name    = 'CRM Profile'
    fk_name         = 'user'  # ✅ yeh add karo
    fields          = ('full_name', 'phone', 'city', 'status', 'department',
                       'avatar_initials', 'login_count', 'action_count')
    readonly_fields = ('avatar_initials', 'login_count', 'action_count')


class ExtendedUserAdmin(BaseUserAdmin):
    inlines         = (UserProfileInline,)
    list_display    = ('email', 'get_full_name_display', 'get_dept', 'get_status', 'is_active', 'date_joined')
    list_filter     = ('is_active', 'is_staff', 'profile__status', 'profile__department')
    search_fields   = ('email', 'profile__full_name', 'profile__city')

    def get_full_name_display(self, obj):
        p = getattr(obj, 'profile', None)
        return p.full_name if p else '-'
    get_full_name_display.short_description = 'Full Name'

    def get_dept(self, obj):
        p = getattr(obj, 'profile', None)
        return p.department.name if p and p.department else '-'
    get_dept.short_description = 'Department'

    def get_status(self, obj):
        p = getattr(obj, 'profile', None)
        return p.status if p else '-'
    get_status.short_description = 'CRM Status'


admin.site.unregister(AuthUser)
admin.site.register(AuthUser, ExtendedUserAdmin)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display        = ['name', 'slug', 'head', 'size', 'color_hex']
    search_fields       = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display    = ['user', 'ip_address', 'city', 'device_info', 'is_active', 'last_activity']
    list_filter     = ['is_active']
    search_fields   = ['user__email', 'user__profile__full_name', 'ip_address']
    readonly_fields = ['created_at', 'last_activity']

    def has_change_permission(self, request, obj=None): return False


@admin.register(UserActivityLog)
class UserActivityLogAdmin(admin.ModelAdmin):
    list_display    = ['actor', 'action', 'target_user', 'description', 'timestamp']
    list_filter     = ['action']
    search_fields   = ['actor__email', 'description']
    readonly_fields = ['actor', 'target_user', 'action', 'description', 'timestamp']

    def has_add_permission(self, request):    return False
    def has_change_permission(self, request, obj=None): return False
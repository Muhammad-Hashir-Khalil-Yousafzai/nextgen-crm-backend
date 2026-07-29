from django.contrib import admin
from .models import Account, AuditLog


# ─── AuditLog Inline (Account ke andar dikhao) ──────────────────────────────
class AuditLogInline(admin.TabularInline):
    model          = AuditLog
    extra          = 0
    readonly_fields= ('action', 'field', 'old_value', 'new_value', 'by', 'at')
    can_delete     = False
    ordering       = ('-at',)

    def has_add_permission(self, request, obj=None):
        return False  # Admin se manually log add nahi hoga


# ─── Account Admin ───────────────────────────────────────────────────────────
@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display   = ('code', 'name', 'type', 'level', 'balance',
                      'budget', 'currency', 'status', 'linked_module', 'updated_at')
    list_filter    = ('type', 'status', 'currency', 'linked_module')
    search_fields  = ('code', 'name', 'note')
    ordering       = ('code',)
    readonly_fields= ('level', 'created_at', 'updated_at', 'budget_utilization_pct')
    raw_id_fields  = ('parent', 'created_by')
    inlines        = [AuditLogInline]

    fieldsets = (
        ('Identity', {
            'fields': ('code', 'name')
        }),
        ('Classification', {
            'fields': ('type', 'parent', 'level')
        }),
        ('Financial', {
            'fields': ('balance', 'budget', 'budget_utilization_pct', 'currency')
        }),
        ('Configuration', {
            'fields': ('status', 'linked_module', 'note')
        }),
        ('Meta', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Budget Used %')
    def budget_utilization_pct(self, obj):
        pct = obj.budget_utilization_pct
        return f"{pct}%" if pct is not None else "—"

    def save_model(self, request, obj, form, change):
        """Auto-set created_by aur level."""
        if not obj.pk:
            obj.created_by = request.user
        obj.level = (obj.parent.level + 1) if obj.parent else 0
        super().save_model(request, obj, form, change)


# ─── AuditLog Admin ──────────────────────────────────────────────────────────
@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display  = ('at', 'account', 'action', 'field', 'old_value', 'new_value', 'by')
    list_filter   = ('action',)
    search_fields = ('account__code', 'account__name', 'by__username')
    ordering      = ('-at',)
    readonly_fields = ('account', 'action', 'field', 'old_value', 'new_value', 'by', 'at')

    def has_add_permission(self, request):
        return False  # Audit logs manually nahi banenge

    def has_change_permission(self, request, obj=None):
        return False  # Audit logs edit nahi honge

    def has_delete_permission(self, request, obj=None):
        return False  # Audit logs delete nahi honge
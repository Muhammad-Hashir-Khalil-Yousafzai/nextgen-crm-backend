from django.contrib import admin
from .models import PayrollRun, PayrollLine

# ❌ REMOVED: fake Employee admin registration
#    HRM ka Employee model apne app (crmapp/admin.py) mein already register hoga.


class PayrollLineInline(admin.TabularInline):
    model = PayrollLine
    extra = 0
    readonly_fields = ('net_pay',)


@admin.register(PayrollRun)
class PayrollRunAdmin(admin.ModelAdmin):
    list_display    = ('month', 'status', 'total_gross', 'total_net', 'total_tax', 'created_at')
    list_filter     = ('status',)
    readonly_fields = ('total_gross', 'total_net', 'total_tax', 'created_at', 'updated_at')
    inlines         = [PayrollLineInline]


@admin.register(PayrollLine)
class PayrollLineAdmin(admin.ModelAdmin):
    list_display  = ('employee', 'run', 'basic', 'allowances', 'deductions', 'tax', 'net_pay')
    search_fields = ('employee__name', 'employee__employee_id')
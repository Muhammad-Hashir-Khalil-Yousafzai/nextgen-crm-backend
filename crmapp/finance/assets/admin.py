from django.contrib import admin
from .models import Asset, AssetAssignment, AssetMaintenance

class AssetAssignmentInline(admin.TabularInline):  model = AssetAssignment; extra = 0
class AssetMaintenanceInline(admin.TabularInline): model = AssetMaintenance; extra = 0

@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display  = ('asset_tag','name','category','status','purchase_cost','vendor_name','purchase_date')
    list_filter   = ('category','status'); search_fields = ('asset_tag','name','serial_number')
    readonly_fields = ('created_at','updated_at')
    inlines = [AssetAssignmentInline, AssetMaintenanceInline]

@admin.register(AssetAssignment)
class AssetAssignmentAdmin(admin.ModelAdmin):
    # ✅ FIXED: employee_name/department text fields nahi rahe — ab employee FK hai
    list_display  = ('asset','employee','assigned_date','returned_date')
    search_fields = ('employee__name','employee__employee_id','asset__asset_tag')

@admin.register(AssetMaintenance)
class AssetMaintenanceAdmin(admin.ModelAdmin):
    list_display  = ('asset','type','cost','performed_by','date','next_due')
    list_filter   = ('type',)
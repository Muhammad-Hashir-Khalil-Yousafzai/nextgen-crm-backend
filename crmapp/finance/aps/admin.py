from django.contrib import admin
from .models import Vendor, Bill, BillItem, APPayment, BillApproval, PurchaseOrder

class BillItemInline(admin.TabularInline):     model = BillItem;     extra = 1
class APPaymentInline(admin.TabularInline):    model = APPayment;    extra = 0; readonly_fields=('amount','date','method'); can_delete=False
class BillApprovalInline(admin.TabularInline): model = BillApproval; extra = 0

@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display  = ('name','company','email','currency','balance','risk')
    list_filter   = ('risk','currency'); search_fields = ('name','company','email')

@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display  = ('number','vendor','amount','paid_amount','status','due_date','category')
    list_filter   = ('status','category'); search_fields = ('number','vendor__name')
    inlines = [BillItemInline, APPaymentInline, BillApprovalInline]
    readonly_fields = ('created_at','updated_at')

@admin.register(PurchaseOrder)
class POAdmin(admin.ModelAdmin):
    list_display  = ('number','vendor','amount','date','status','bill')
    list_filter   = ('status',); search_fields = ('number','vendor__name')
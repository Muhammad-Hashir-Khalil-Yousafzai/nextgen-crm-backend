from django.contrib import admin
from .models import Customer, Invoice, InvoiceItem, ARPayment, Dispute

class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem; extra = 1

class ARPaymentInline(admin.TabularInline):
    model = ARPayment; extra = 0; readonly_fields = ('amount','date','method'); can_delete = False
    def has_add_permission(self, request, obj=None): return False

class DisputeInline(admin.TabularInline):
    model = Dispute; extra = 0

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display  = ('name','company','email','credit_limit','balance','risk')
    list_filter   = ('risk',); search_fields = ('name','company','email')

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display  = ('invoice_no','customer','amount','paid_amount','status','due_date')
    list_filter   = ('status',); search_fields = ('invoice_no','customer__name')
    inlines = [InvoiceItemInline, ARPaymentInline, DisputeInline]
    readonly_fields = ('created_at','updated_at')
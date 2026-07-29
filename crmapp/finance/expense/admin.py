from django.contrib import admin
from .models import ExpenseCategory, ExpenseClaim


class ExpenseClaimInline(admin.TabularInline):
    model = ExpenseClaim; extra = 0
    readonly_fields = ('employee','amount','date','status','created_at'); can_delete = False
    def has_add_permission(self, request, obj=None): return False


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display  = ('code','name','level','budget','spent','gl_account')
    list_filter   = ('level',); search_fields = ('code','name')
    raw_id_fields = ('parent','gl_account'); inlines = [ExpenseClaimInline]


@admin.register(ExpenseClaim)
class ExpenseClaimAdmin(admin.ModelAdmin):
    list_display  = ('id','employee','category','amount','date','status','created_at')
    list_filter   = ('status','category'); search_fields = ('employee__name','notes')
    readonly_fields = ('created_at','updated_at'); raw_id_fields = ('employee','category')
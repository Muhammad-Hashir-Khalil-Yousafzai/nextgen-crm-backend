from django.contrib import admin
from .models import BankAccount, CashAccount, Transaction, Cheque, BankReconciliation

class TransactionInline(admin.TabularInline):
    model = Transaction; extra = 0; can_delete = False
    readonly_fields = ('type','amount','date','description','created_at')
    def has_add_permission(self, request, obj=None): return False

@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display  = ('bank_name','account_number','branch','currency','current_balance','status')
    list_filter   = ('status','currency'); search_fields = ('bank_name','account_number')
    inlines       = [TransactionInline]

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display  = ('date','bank_account','type','amount','description','reference')
    list_filter   = ('type','category'); search_fields = ('description','reference')
    readonly_fields = ('created_at',)

@admin.register(Cheque)
class ChequeAdmin(admin.ModelAdmin):
    list_display  = ('number','payee','amount','bank_account','issue_date','due_date','status')
    list_filter   = ('status',); search_fields = ('number','payee')

@admin.register(BankReconciliation)
class ReconciliationAdmin(admin.ModelAdmin):
    list_display  = ('date','bank_account','description','system_amt','bank_amt','status')
    list_filter   = ('status',)
from rest_framework import serializers
from .models import BankAccount, CashAccount, Transaction, Cheque, BankReconciliation


class BankAccountSerializer(serializers.ModelSerializer):
    transactions_count = serializers.SerializerMethodField()
    class Meta:
        model  = BankAccount
        fields = ['id','bank_name','account_number','branch','currency','iban','swift',
                  'opening_balance','current_balance','status','color','created_at','transactions_count']
        read_only_fields = ['created_at']
    def get_transactions_count(self, obj): return obj.transactions.count()


class CashAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model  = CashAccount
        fields = ['id','name','branch','balance','currency']


class TransactionSerializer(serializers.ModelSerializer):
    bank_name = serializers.SerializerMethodField()
    class Meta:
        model  = Transaction
        fields = ['id','bank_account','bank_name','type','amount','date','description','method','reference','category','created_at']
        read_only_fields = ['created_at']
    def get_bank_name(self, obj): return obj.bank_account.bank_name


class ChequeSerializer(serializers.ModelSerializer):
    bank_name = serializers.SerializerMethodField()
    class Meta:
        model  = Cheque
        fields = ['id','bank_account','bank_name','number','payee','amount','issue_date','due_date','status','reference']
    def get_bank_name(self, obj): return obj.bank_account.bank_name


class BankReconciliationSerializer(serializers.ModelSerializer):
    class Meta:
        model  = BankReconciliation
        fields = ['id','bank_account','date','description','system_amt','bank_amt','status']
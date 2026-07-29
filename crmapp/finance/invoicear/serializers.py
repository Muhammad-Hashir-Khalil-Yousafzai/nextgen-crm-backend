from rest_framework import serializers
from .models import Customer, Invoice, InvoiceItem, ARPayment, Dispute


class InvoiceItemSerializer(serializers.ModelSerializer):
    total = serializers.ReadOnlyField()
    class Meta:
        model  = InvoiceItem
        fields = ['id','invoice','description','qty','rate','total']


class ARPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ARPayment
        fields = ['id','invoice','amount','date','method']


class DisputeSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Dispute
        fields = ['id','invoice','reason','status','note','created_at']
        read_only_fields = ['created_at']


class InvoiceSerializer(serializers.ModelSerializer):
    outstanding   = serializers.ReadOnlyField()
    customer_name = serializers.SerializerMethodField()
    items_count   = serializers.SerializerMethodField()
    class Meta:
        model  = Invoice
        fields = ['id','invoice_no','customer','customer_name','amount','paid_amount',
                  'outstanding','invoice_date','due_date','status','notes',
                  'created_at','updated_at','items_count']
        read_only_fields = ['created_at','updated_at']
    def get_customer_name(self, obj): return obj.customer.name
    def get_items_count(self, obj):   return obj.items.count()


class InvoiceDetailSerializer(InvoiceSerializer):
    items    = InvoiceItemSerializer(many=True, read_only=True)
    payments = ARPaymentSerializer(many=True, read_only=True)
    disputes = DisputeSerializer(many=True, read_only=True)
    class Meta(InvoiceSerializer.Meta):
        fields = InvoiceSerializer.Meta.fields + ['items','payments','disputes']


class CustomerSerializer(serializers.ModelSerializer):
    invoices_count = serializers.SerializerMethodField()
    class Meta:
        model  = Customer
        fields = ['id','name','company','email','phone','credit_limit',
                  'payment_terms','balance','risk','avatar_url','created_at','invoices_count']
        read_only_fields = ['created_at']
    def get_invoices_count(self, obj): return obj.invoices.count()


class CustomerDetailSerializer(CustomerSerializer):
    invoices = InvoiceSerializer(many=True, read_only=True)
    class Meta(CustomerSerializer.Meta):
        fields = CustomerSerializer.Meta.fields + ['invoices']
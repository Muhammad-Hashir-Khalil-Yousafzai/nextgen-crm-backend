from rest_framework import serializers
from .models import Vendor, Bill, BillItem, APPayment, BillApproval, PurchaseOrder

class BillItemSerializer(serializers.ModelSerializer):
    total = serializers.ReadOnlyField()
    class Meta:
        model = BillItem
        fields = ['id', 'description', 'qty', 'rate', 'total']

class APPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = APPayment
        fields = ['id', 'bill', 'amount', 'date', 'method']

class BillApprovalSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillApproval
        fields = ['id', 'bill', 'role', 'name', 'status', 'date', 'note']

class BillSerializer(serializers.ModelSerializer):
    outstanding = serializers.ReadOnlyField()
    vendor_name = serializers.SerializerMethodField()
    items_count = serializers.SerializerMethodField()
    items = BillItemSerializer(many=True, required=False)

    class Meta:
        model = Bill
        fields = [
            'id', 'number', 'vendor', 'vendor_name', 'invoice_ref', 'amount', 'paid_amount',
            'outstanding', 'tax', 'bill_date', 'due_date', 'status', 'category', 'notes',
            'created_at', 'updated_at', 'items_count', 'items'
        ]
        read_only_fields = ['created_at', 'updated_at', 'amount'] 

    def get_vendor_name(self, obj):
        return obj.vendor.name if obj.vendor else None

    def get_items_count(self, obj):
        return obj.items.count()

class BillDetailSerializer(BillSerializer):
    payments = APPaymentSerializer(many=True, read_only=True)
    approvals = BillApprovalSerializer(many=True, read_only=True)

    class Meta(BillSerializer.Meta):
        fields = BillSerializer.Meta.fields + ['payments', 'approvals']

class VendorSerializer(serializers.ModelSerializer):
    bills_count = serializers.SerializerMethodField()
    class Meta:
        model = Vendor
        fields = [
            'id', 'name', 'company', 'email', 'phone', 'tax_id', 'address',
            'terms', 'currency', 'balance', 'risk', 'avatar_url', 'created_at', 'bills_count'
        ]
        read_only_fields = ['created_at']

    def get_bills_count(self, obj):
        return obj.bills.count()

class PurchaseOrderSerializer(serializers.ModelSerializer):
    vendor_name = serializers.SerializerMethodField()
    class Meta:
        model = PurchaseOrder
        fields = ['id', 'number', 'vendor', 'vendor_name', 'bill', 'amount', 'date', 'status']

    def get_vendor_name(self, obj):
        return obj.vendor.name if obj.vendor else None
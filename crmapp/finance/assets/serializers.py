from rest_framework import serializers
from .models import Asset, AssetAssignment, AssetMaintenance
from crmapp.models import Employee

class AssetAssignmentSerializer(serializers.ModelSerializer):
    is_active     = serializers.ReadOnlyField()
    employee_name = serializers.SerializerMethodField()
    department    = serializers.ReadOnlyField()

    class Meta:
        model  = AssetAssignment
        fields = ['id', 'asset', 'employee', 'employee_name', 'department',
                  'assigned_date', 'returned_date', 'is_active']

    # ✅ FIX: Employee ko PrimaryKeyRelatedField banaya taake validate ho sake
    def get_employee_name(self, obj):
        return obj.employee.full_name or obj.employee.name


class AssetMaintenanceSerializer(serializers.ModelSerializer):
    class Meta:
        model  = AssetMaintenance
        fields = ['id', 'asset', 'type', 'cost', 'performed_by', 'date', 'next_due', 'notes']


class AssetSerializer(serializers.ModelSerializer):
    current_assignment = serializers.SerializerMethodField()
    maintenance_count  = serializers.SerializerMethodField()

    class Meta:
        model  = Asset
        fields = ['id', 'asset_tag', 'name', 'category', 'serial_number', 'purchase_date',
                  'purchase_cost', 'vendor_name', 'status', 'notes', 'created_at', 'updated_at',
                  'current_assignment', 'maintenance_count']
        read_only_fields = ['created_at', 'updated_at']

    def get_current_assignment(self, obj):
        a = obj.assignments.filter(returned_date__isnull=True).first()
        return AssetAssignmentSerializer(a).data if a else None

    def get_maintenance_count(self, obj):
        return obj.maintenance_history.count()


class AssetDetailSerializer(AssetSerializer):
    assignments         = AssetAssignmentSerializer(many=True, read_only=True)
    maintenance_history = AssetMaintenanceSerializer(many=True, read_only=True)

    class Meta(AssetSerializer.Meta):
        fields = AssetSerializer.Meta.fields + ['assignments', 'maintenance_history']
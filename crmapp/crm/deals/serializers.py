from rest_framework import serializers
from .models import Deal


class DealSerializer(serializers.ModelSerializer):
    """Full serializer — used for create / update / retrieve."""

    company_display = serializers.ReadOnlyField()
    weighted_value   = serializers.ReadOnlyField()

    # Nested read-only summaries so the frontend can display names without
    # separate lookups
    contact_name  = serializers.SerializerMethodField()
    pipeline_name = serializers.SerializerMethodField()
    lead_name     = serializers.SerializerMethodField()

    class Meta:
        model  = Deal
        fields = '__all__'
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'created_by',
            'company_display', 'weighted_value',
            'contact_name', 'pipeline_name', 'lead_name',
        ]

    def get_contact_name(self, obj):
        return obj.contact.name if obj.contact else None

    def get_pipeline_name(self, obj):
        return obj.pipeline.name if obj.pipeline else None

    def get_lead_name(self, obj):
        return obj.lead.name if obj.lead else None


class DealListSerializer(serializers.ModelSerializer):
    """Lightweight serializer — used for list / kanban board."""

    company_display = serializers.ReadOnlyField()
    weighted_value   = serializers.ReadOnlyField()

    class Meta:
        model  = Deal
        fields = [
            'id', 'title', 'code', 'value', 'probability',
            'stage', 'tags', 'email', 'phone', 'location',
            'assigned_to', 'assignee_avatar',
            'close_date', 'company_display', 'company_name',
            'company', 'contact', 'pipeline', 'lead',
            'weighted_value', 'created_at',
        ]
from rest_framework import serializers
from .models import Lead, LeadNote


class LeadNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model  = LeadNote
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class LeadSerializer(serializers.ModelSerializer):
    weighted_value       = serializers.ReadOnlyField()
    company_display      = serializers.SerializerMethodField()
    contact_display      = serializers.SerializerMethodField()
    notes_list           = LeadNoteSerializer(source='lead_notes', many=True, read_only=True)

    class Meta:
        model  = Lead
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by', 'initials']

    def get_company_display(self, obj):
        if obj.company:
            return obj.company.name
        return obj.company_name

    def get_contact_display(self, obj):
        if obj.contact:
            return obj.contact.name
        return ''


class LeadListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views"""
    weighted_value  = serializers.ReadOnlyField()
    company_display = serializers.SerializerMethodField()

    class Meta:
        model  = Lead
        fields = [
            'id', 'name', 'initials', 'email', 'phone', 'location',
            'company_name', 'company_display', 'value', 'weighted_value',
            'probability', 'score', 'status', 'priority', 'source',
            'deal_stage', 'assigned_to', 'last_contact', 'next_action',
            'tags', 'notes_count', 'activities', 'lost_reason',
            'created_at',
        ]

    def get_company_display(self, obj):
        if obj.company:
            return obj.company.name
        return obj.company_name

from rest_framework import serializers
from .models import Company


class CompanySerializer(serializers.ModelSerializer):
    contacts_count = serializers.SerializerMethodField()
    open_deals     = serializers.SerializerMethodField()

    class Meta:
        model  = Company
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']

    def get_contacts_count(self, obj):
        return obj.contacts.count()

    def get_open_deals(self, obj):
        return 0  # extend when deals app is built


class CompanyListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for dropdowns"""
    class Meta:
        model  = Company
        fields = ['id', 'name', 'code', 'industry', 'type']

from rest_framework import serializers
from .models import Contract


class ContractSerializer(serializers.ModelSerializer):
    days_until_expiry = serializers.ReadOnlyField()
    renewal_urgency   = serializers.ReadOnlyField()

    class Meta:
        model  = Contract
        fields = '__all__'
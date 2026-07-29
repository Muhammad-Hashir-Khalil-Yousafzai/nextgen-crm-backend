from rest_framework import serializers
from .models import Pipeline


class PipelineSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Pipeline
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']

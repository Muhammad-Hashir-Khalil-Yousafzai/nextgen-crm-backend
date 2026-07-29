from rest_framework import serializers
from .models import Survey, SurveyResponse


class SurveyResponseSerializer(serializers.ModelSerializer):
    sentiment_label = serializers.ReadOnlyField()
    nps_category    = serializers.ReadOnlyField()

    class Meta:
        model  = SurveyResponse
        fields = '__all__'


class SurveySerializer(serializers.ModelSerializer):
    response_rate = serializers.ReadOnlyField()
    # Inline responses when viewing a single survey (read-only)
    responses_data = SurveyResponseSerializer(
        source='responses', many=True, read_only=True
    )

    class Meta:
        model  = Survey
        fields = '__all__'
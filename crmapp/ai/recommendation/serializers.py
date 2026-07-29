"""
crmapp/ai/recommendation/serializers.py
"""

from rest_framework import serializers
from .models import (
    UserProfile,
    RecommendationItem,
    FeedbackEvent,
    ABTest,
    ABTestAssignment,
    ChannelPerformance,
    ModelPerformance,
    ProactiveAlert,
)


class UserProfileSerializer(serializers.ModelSerializer):
    segment_display = serializers.SerializerMethodField()

    class Meta:
        model  = UserProfile
        fields = [
            "id", "subject_type", "subject_id", "subject_name", "subject_email",
            "engagement_score", "churn_risk_score", "ltv_estimate", "purchase_count",
            "segment", "segment_display", "top_category", "preferred_channel",
            "last_emotion", "last_emotion_score",
            "xai_conversion_prob", "xai_deal_win_prob",
            "last_computed_at", "created_at",
        ]

    def get_segment_display(self, obj):
        return obj.get_segment_display()


class RecommendationItemSerializer(serializers.ModelSerializer):
    subject_name  = serializers.CharField(source="profile.subject_name", read_only=True)
    subject_email = serializers.CharField(source="profile.subject_email", read_only=True)
    segment       = serializers.CharField(source="profile.segment", read_only=True)

    class Meta:
        model  = RecommendationItem
        fields = [
            "id", "profile_id",
            "subject_name", "subject_email", "segment",
            "rec_type", "title", "description", "action_url",
            "relevance_score", "revenue_impact", "confidence",
            "model_used", "channel", "status",
            "reasons", "trigger_signals",
            "is_proactive", "proactive_alert_id",
            "delivered_at", "expires_at",
            "created_at", "updated_at",
        ]


class FeedbackEventSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="profile.subject_name", read_only=True)
    rec_title    = serializers.CharField(source="recommendation.title", read_only=True)

    class Meta:
        model  = FeedbackEvent
        fields = [
            "id", "recommendation_id", "profile_id",
            "subject_name", "rec_title",
            "action", "signal_type", "weight",
            "revenue_realised", "recorded_at",
        ]


class ABTestSerializer(serializers.ModelSerializer):
    duration_days = serializers.SerializerMethodField()

    class Meta:
        model  = ABTest
        fields = [
            "id", "name", "description",
            "control_label", "treatment_label",
            "primary_metric", "status",
            "winner", "lift", "confidence", "sample_size",
            "duration_days",
            "started_at", "ended_at", "created_at",
        ]

    def get_duration_days(self, obj):
        return obj.duration_days


class ChannelPerformanceSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ChannelPerformance
        fields = [
            "id", "channel", "date",
            "recs_delivered", "recs_clicked", "recs_converted",
            "ctr", "conv_rate", "revenue",
        ]


class ModelPerformanceSerializer(serializers.ModelSerializer):
    month_name = serializers.SerializerMethodField()

    class Meta:
        model  = ModelPerformance
        fields = [
            "id", "model_name", "year", "month", "month_name",
            "recs_total", "ctr", "conv_rate", "revenue", "precision",
            "computed_at",
        ]

    def get_month_name(self, obj):
        import calendar
        return calendar.month_abbr[obj.month]


class ProactiveAlertSerializer(serializers.ModelSerializer):
    subject_name  = serializers.CharField(source="profile.subject_name", read_only=True)
    subject_email = serializers.CharField(source="profile.subject_email", read_only=True)
    segment       = serializers.CharField(source="profile.segment", read_only=True)
    recs_count    = serializers.SerializerMethodField()

    class Meta:
        model  = ProactiveAlert
        fields = [
            "id", "profile_id",
            "subject_name", "subject_email", "segment",
            "trigger_type", "severity", "summary",
            "signal_data", "resolved", "resolved_at",
            "fired_at", "recs_count",
        ]

    def get_recs_count(self, obj):
        return obj.recommendations.count()


# ── Lightweight serializers for list views ────────────────────────────────────

class RecommendationListSerializer(serializers.ModelSerializer):
    """Slimmed-down version for the list endpoint."""
    subject_name = serializers.CharField(source="profile.subject_name", read_only=True)

    class Meta:
        model  = RecommendationItem
        fields = [
            "id", "subject_name",
            "rec_type", "title",
            "relevance_score", "channel", "status",
            "model_used", "is_proactive",
            "created_at",
        ]


class DashboardStatsSerializer(serializers.Serializer):
    recs_served_today       = serializers.IntegerField()
    ctr                     = serializers.FloatField()
    conv_rate               = serializers.FloatField()
    revenue_today           = serializers.FloatField()
    model_precision         = serializers.FloatField()
    active_ab_tests         = serializers.IntegerField()
    open_proactive_alerts   = serializers.IntegerField()
    total_profiles          = serializers.IntegerField()
    at_risk_profiles        = serializers.IntegerField()
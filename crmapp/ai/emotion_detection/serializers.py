from rest_framework import serializers
from .models import GmailConnection, EmotionDetection, AlertRule, AlertLog


class GmailConnectionSerializer(serializers.ModelSerializer):
    class Meta:
        model  = GmailConnection
        fields = [
            "id",
            "gmail_address",
            "is_active",
            "sync_interval",
            "sender_filter",
            "last_synced_at",
            "connected_at",
        ]
        read_only_fields = ["connected_at", "last_synced_at"]


class EmotionDetectionSerializer(serializers.ModelSerializer):
    confidence_pct  = serializers.SerializerMethodField()
    time            = serializers.SerializerMethodField()
    gmail_address   = serializers.SerializerMethodField()   # NEW

    class Meta:
        model  = EmotionDetection
        fields = [
            "id",
            "customer_name",
            "customer_email",
            "email_subject",
            "email_body_snippet",
            "emotion",
            "intensity",
            "confidence",
            "confidence_pct",
            "action_taken",
            "alert_fired",
            "detected_at",
            "time",
            "gmail_address",   # NEW
        ]

    def get_confidence_pct(self, obj):
        return obj.confidence_pct

    def get_time(self, obj):
        return obj.detected_at.strftime("%H:%M:%S")

    def get_gmail_address(self, obj):
        return obj.gmail_connection.gmail_address if obj.gmail_connection else None


class AlertRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model  = AlertRule
        fields = [
            "id",
            "emotion",
            "threshold",
            "action",
            "channel",
            "is_enabled",
            "created_at",
        ]
        read_only_fields = ["created_at"]


class AlertLogSerializer(serializers.ModelSerializer):
    customer_email = serializers.SerializerMethodField()
    customer_name  = serializers.SerializerMethodField()
    emotion        = serializers.SerializerMethodField()
    time           = serializers.SerializerMethodField()

    class Meta:
        model  = AlertLog
        fields = [
            "id",
            "action",
            "channel",
            "status",
            "fired_at",
            "time",
            "customer_email",
            "customer_name",
            "emotion",
            "error_msg",
        ]

    def get_customer_email(self, obj):
        return obj.detection.customer_email if obj.detection else ""

    def get_customer_name(self, obj):
        return obj.detection.customer_name if obj.detection else ""

    def get_emotion(self, obj):
        return obj.detection.emotion if obj.detection else "neutral"

    def get_time(self, obj):
        return obj.fired_at.strftime("%H:%M")


# ── Dashboard summary serializer (for KPI strip) ─────────────────────────────

class DashboardStatsSerializer(serializers.Serializer):
    emails_today      = serializers.IntegerField()
    alerts_triggered  = serializers.IntegerField()
    avg_confidence    = serializers.FloatField()
    customers_tracked = serializers.IntegerField()
    dominant_emotion  = serializers.CharField()
    negative_rate     = serializers.FloatField()
    gmail_connected   = serializers.BooleanField()
    last_synced_at    = serializers.DateTimeField(allow_null=True)

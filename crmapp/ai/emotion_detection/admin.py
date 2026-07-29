from django.contrib import admin
from .models import GmailConnection, EmotionDetection, AlertRule, AlertLog


@admin.register(GmailConnection)
class GmailConnectionAdmin(admin.ModelAdmin):
    list_display  = ["user", "gmail_address", "is_active", "sync_interval", "last_synced_at", "connected_at"]
    list_filter   = ["is_active"]
    search_fields = ["user__email", "gmail_address"]
    readonly_fields = ["connected_at", "last_synced_at"]


@admin.register(EmotionDetection)
class EmotionDetectionAdmin(admin.ModelAdmin):
    list_display  = ["customer_email", "customer_name", "emotion", "intensity", "confidence_pct", "alert_fired", "detected_at"]
    list_filter   = ["emotion", "intensity", "alert_fired"]
    search_fields = ["customer_email", "customer_name", "email_subject"]
    readonly_fields = ["detected_at", "gmail_message_id"]
    ordering      = ["-detected_at"]


@admin.register(AlertRule)
class AlertRuleAdmin(admin.ModelAdmin):
    list_display  = ["user", "emotion", "threshold", "action", "channel", "is_enabled"]
    list_filter   = ["emotion", "threshold", "channel", "is_enabled"]
    search_fields = ["user__email", "action"]


@admin.register(AlertLog)
class AlertLogAdmin(admin.ModelAdmin):
    list_display  = ["action", "channel", "status", "fired_at"]
    list_filter   = ["status", "channel"]
    readonly_fields = ["fired_at"]

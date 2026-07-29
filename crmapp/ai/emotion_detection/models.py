from django.db import models
from django.conf import settings


# ── 1. Gmail Connection ───────────────────────────────────────────────────────
# Multiple per business (CRM user). Each business can connect several Gmail
# inboxes (e.g. support@, sales@). Each is synced independently.

class GmailConnection(models.Model):
    user            = models.ForeignKey(
                          settings.AUTH_USER_MODEL,
                          on_delete=models.CASCADE,
                          related_name="gmail_connections"   # plural now
                      )
    gmail_address   = models.EmailField()
    access_token    = models.TextField()
    refresh_token   = models.TextField()
    token_expiry    = models.DateTimeField(null=True, blank=True)
    is_active       = models.BooleanField(default=True)
    sync_interval   = models.IntegerField(default=10)
    sender_filter   = models.CharField(max_length=255, blank=True, null=True)
    last_synced_at  = models.DateTimeField(null=True, blank=True)
    connected_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Gmail Connection"
        verbose_name_plural = "Gmail Connections"
        unique_together     = ("user", "gmail_address")   # prevent duplicate same-email connections
        ordering            = ["-connected_at"]

    def __str__(self):
        return f"{self.user} → {self.gmail_address}"


# ── 2. Emotion Detection ──────────────────────────────────────────────────────
# Now also linked to WHICH Gmail connection the email came from.

class EmotionDetection(models.Model):

    EMOTION_CHOICES = [
        ("happy",     "Happy"),
        ("sad",       "Sad"),
        ("angry",     "Angry"),
        ("fearful",   "Fearful"),
        ("surprised", "Surprised"),
        ("neutral",   "Neutral"),
    ]

    INTENSITY_CHOICES = [
        ("high",   "High"),
        ("medium", "Medium"),
        ("low",    "Low"),
    ]

    user              = models.ForeignKey(
                            settings.AUTH_USER_MODEL,
                            on_delete=models.CASCADE,
                            related_name="emotion_detections"
                        )

    # NEW — which Gmail inbox this email came from
    gmail_connection  = models.ForeignKey(
                            GmailConnection,
                            on_delete=models.CASCADE,
                            related_name="detections",
                            null=True, blank=True
                        )

    customer_name     = models.CharField(max_length=255, blank=True)
    customer_email    = models.EmailField()

    email_subject     = models.CharField(max_length=500, blank=True)
    email_body_snippet= models.TextField(blank=True)
    gmail_message_id  = models.CharField(max_length=255, unique=True)

    emotion           = models.CharField(max_length=20, choices=EMOTION_CHOICES)
    intensity         = models.CharField(max_length=10, choices=INTENSITY_CHOICES)
    confidence        = models.FloatField()

    action_taken      = models.CharField(max_length=255, blank=True, null=True)
    alert_fired       = models.BooleanField(default=False)

    detected_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Emotion Detection"
        verbose_name_plural = "Emotion Detections"
        ordering            = ["-detected_at"]
        indexes             = [
            models.Index(fields=["user", "detected_at"]),
            models.Index(fields=["user", "emotion"]),
            models.Index(fields=["customer_email"]),
        ]

    def __str__(self):
        return f"{self.customer_email} → {self.emotion} ({self.confidence:.0%})"

    @property
    def confidence_pct(self):
        return round(self.confidence * 100)


# ── 3. Alert Rule ─────────────────────────────────────────────────────────────

class AlertRule(models.Model):

    EMOTION_CHOICES = EmotionDetection.EMOTION_CHOICES

    INTENSITY_CHOICES = [
        ("high",   "High"),
        ("medium", "Medium"),
        ("low",    "Low"),
    ]

    CHANNEL_CHOICES = [
        ("slack",  "Slack"),
        ("email",  "Email"),
        ("in_app", "In-App"),
        ("crm",    "CRM"),
    ]

    user        = models.ForeignKey(
                      settings.AUTH_USER_MODEL,
                      on_delete=models.CASCADE,
                      related_name="alert_rules"
                  )
    emotion     = models.CharField(max_length=20, choices=EMOTION_CHOICES)
    threshold   = models.CharField(max_length=10, choices=INTENSITY_CHOICES)
    action      = models.CharField(max_length=255)
    channel     = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    is_enabled  = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Alert Rule"
        verbose_name_plural = "Alert Rules"
        ordering            = ["emotion", "threshold"]

    def __str__(self):
        return f"{self.user} | {self.emotion} ≥ {self.threshold} → {self.action}"


# ── 4. Alert Log ──────────────────────────────────────────────────────────────

class AlertLog(models.Model):

    STATUS_CHOICES = [
        ("actioned", "Actioned"),
        ("pending",  "Pending"),
        ("failed",   "Failed"),
    ]

    rule        = models.ForeignKey(
                      AlertRule,
                      on_delete=models.SET_NULL,
                      null=True,
                      related_name="logs"
                  )
    detection   = models.ForeignKey(
                      EmotionDetection,
                      on_delete=models.CASCADE,
                      related_name="alert_logs"
                  )
    action      = models.CharField(max_length=255)
    channel     = models.CharField(max_length=20)
    status      = models.CharField(max_length=20,
                      choices=STATUS_CHOICES, default="pending")
    fired_at    = models.DateTimeField(auto_now_add=True)
    error_msg   = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name        = "Alert Log"
        verbose_name_plural = "Alert Logs"
        ordering            = ["-fired_at"]

    def __str__(self):
        return f"{self.action} — {self.status} at {self.fired_at:%H:%M}"
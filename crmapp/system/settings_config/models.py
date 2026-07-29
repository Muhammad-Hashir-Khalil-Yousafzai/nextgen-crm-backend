# settings_config/models.py
from django.db import models
from django.contrib.auth.models import User as AuthUser


class SystemSetting(models.Model):
    """
    Singleton (pk=1). General + Branding + Modules + Features tabs.
    Frontend gen, brand, modules, features state objects all map here.
    """
    THEME_CHOICES = [('light','Light'),('dark','Dark'),('system','System Default')]

    # ── General tab ──
    system_name   = models.CharField(max_length=100, default='NextCRM')
    company_name  = models.CharField(max_length=200, default='')
    timezone      = models.CharField(max_length=60,  default='Asia/Karachi')
    language      = models.CharField(max_length=20,  default='en')
    date_format   = models.CharField(max_length=20,  default='DD/MM/YYYY')
    currency      = models.CharField(max_length=10,  default='PKR')
    fiscal_year   = models.CharField(max_length=20,  default='Jan-Dec')

    # ── Branding tab ──
    primary_color = models.CharField(max_length=9,   default='#3a9aab')
    theme         = models.CharField(max_length=8,   choices=THEME_CHOICES, default='light')
    logo_url      = models.CharField(max_length=300, blank=True)
    favicon_url   = models.CharField(max_length=300, blank=True)

    # ── Modules tab — {crm:true, hr:true, finance:true, ...} ──
    module_config = models.JSONField(default=dict)

    # ── Features tab — {darkMode:false, aiAssist:false, ...} ──
    feature_flags = models.JSONField(default=dict)

    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        AuthUser, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='system_setting_updates'
    )

    class Meta:
        db_table = 'system_settings'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1, defaults={
            'module_config': {
                'crm': True, 'hr': True, 'finance': True,
                'marketing': True, 'analytics': True, 'ai': False,
            },
            'feature_flags': {
                'darkMode': False, 'aiAssist': False,
                'advancedReporting': True, 'emailIntegration': True,
                'smsNotifications': False, 'biometricAuth': False,
                'dataExport': True, 'customDashboard': True,
            },
        })
        return obj


class NotificationSetting(models.Model):
    """Singleton. Notifications tab — channels + event toggles."""
    # Channels
    email_notif   = models.BooleanField(default=True)
    sms_notif     = models.BooleanField(default=False)
    push_notif    = models.BooleanField(default=True)
    in_app_notif  = models.BooleanField(default=True)
    # Events
    new_lead      = models.BooleanField(default=True)
    task_assigned = models.BooleanField(default=True)
    deal_closed   = models.BooleanField(default=True)
    invoice_due   = models.BooleanField(default=True)
    invoice_paid  = models.BooleanField(default=True)
    login_alert   = models.BooleanField(default=True)
    new_contact   = models.BooleanField(default=False)
    report_ready  = models.BooleanField(default=True)
    system_error  = models.BooleanField(default=True)
    maintenance   = models.BooleanField(default=True)
    weekly_report = models.BooleanField(default=True)
    monthly_report = models.BooleanField(default=False)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'notification_settings'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class EmailConfig(models.Model):
    """Singleton. Email tab — SMTP configuration."""
    ENCRYPTION_CHOICES = [('tls','TLS'),('ssl','SSL'),('none','None')]

    smtp_host     = models.CharField(max_length=200, default='smtp.gmail.com')
    smtp_port     = models.PositiveIntegerField(default=587)
    smtp_user     = models.EmailField(default='')
    smtp_password = models.CharField(max_length=300, blank=True)   # encrypt in production
    encryption    = models.CharField(max_length=4, choices=ENCRYPTION_CHOICES, default='tls')
    sender_name   = models.CharField(max_length=100, default='NextCRM')
    sender_email  = models.EmailField(default='')
    reply_to      = models.EmailField(blank=True)
    is_verified   = models.BooleanField(default=False)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'email_configs'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class IntegrationKey(models.Model):
    """Integrations tab — third-party API keys (Stripe, Twilio, etc.)"""
    STATUS_CHOICES = [('active','Active'),('inactive','Inactive'),('error','Error')]

    name          = models.CharField(max_length=100)
    icon_label    = models.CharField(max_length=10, default='?')
    color_hex     = models.CharField(max_length=9,  default='#3a9aab')
    key_encrypted = models.CharField(max_length=500, blank=True)   # encrypt in production
    status        = models.CharField(max_length=10, choices=STATUS_CHOICES, default='inactive')
    call_count    = models.PositiveIntegerField(default=0)
    last_used_at  = models.DateTimeField(null=True, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'integration_keys'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.status})'


class BackupRecord(models.Model):
    """Backup tab — history of all backup runs."""
    TYPE_CHOICES   = [('auto','Automatic'),('manual','Manual')]
    STATUS_CHOICES = [('completed','Completed'),('running','Running'),('failed','Failed')]

    name         = models.CharField(max_length=200)
    size_bytes   = models.BigIntegerField(default=0)
    size_display = models.CharField(max_length=20)         # '2.4 GB'
    backup_type  = models.CharField(max_length=8, choices=TYPE_CHOICES, default='auto')
    status       = models.CharField(max_length=10, choices=STATUS_CHOICES, default='running')
    file_path    = models.CharField(max_length=500, blank=True)
    error_msg    = models.TextField(blank=True)
    initiated_by = models.ForeignKey(
        AuthUser, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='backups_initiated'
    )
    created_at   = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'backup_records'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.status})'
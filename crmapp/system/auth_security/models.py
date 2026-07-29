# auth_security/models.py
from django.db import models
from django.contrib.auth.models import User as AuthUser


class LoginLog(models.Model):
    STATUS_CHOICES = [
        ('success',    'Success'),
        ('failed',     'Failed'),
        ('locked',     'Account Locked'),
        ('suspicious', 'Suspicious'),
    ]
    user             = models.ForeignKey(AuthUser, null=True, blank=True,
                        on_delete=models.SET_NULL, related_name='login_logs')
    email_attempted  = models.CharField(max_length=254, db_index=True)
    status           = models.CharField(max_length=12, choices=STATUS_CHOICES, db_index=True)
    ip_address       = models.GenericIPAddressField(null=True, blank=True)
    city             = models.CharField(max_length=60,  blank=True)
    device_info      = models.CharField(max_length=200, blank=True)
    mfa_used         = models.BooleanField(default=False)
    session_duration = models.CharField(max_length=20,  blank=True)
    timestamp        = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'login_logs'
        ordering = ['-timestamp']

    def __str__(self):
        return f'{self.email_attempted} — {self.status}'


class MFAUser(models.Model):
    METHOD_CHOICES = [
        ('totp',  'Authenticator App'),
        ('sms',   'SMS OTP'),
        ('email', 'Email OTP'),
        ('bio',   'Biometric'),
    ]
    user          = models.OneToOneField(AuthUser, on_delete=models.CASCADE, related_name='mfa')
    mfa_enabled   = models.BooleanField(default=False)
    method        = models.CharField(max_length=10, choices=METHOD_CHOICES, default='totp')
    totp_secret   = models.CharField(max_length=64, blank=True)
    backup_codes  = models.JSONField(default=list)
    last_verified = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'mfa_users'

    def __str__(self):
        return f'{self.user.email} — MFA {"ON" if self.mfa_enabled else "OFF"}'

    @property
    def backup_codes_remaining(self):
        return len(self.backup_codes)


class APIToken(models.Model):
    STATUS_CHOICES = [
        ('active',   'Active'),
        ('expiring', 'Expiring Soon'),
        ('revoked',  'Revoked'),
    ]
    name         = models.CharField(max_length=100)
    token_hash   = models.CharField(max_length=128, unique=True)
    token_prefix = models.CharField(max_length=30)
    scopes       = models.JSONField(default=list)
    created_by   = models.ForeignKey(AuthUser, null=True, blank=True,
                    on_delete=models.SET_NULL, related_name='api_tokens')
    status       = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active', db_index=True)
    call_count   = models.PositiveIntegerField(default=0)
    created_at   = models.DateField(auto_now_add=True)
    expires_at   = models.DateField()
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'api_tokens'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.status})'


class SSOProvider(models.Model):
    PROTOCOL_CHOICES = [('oauth2', 'OAuth 2.0'), ('saml2', 'SAML 2.0')]
    name          = models.CharField(max_length=80)
    icon_label    = models.CharField(max_length=10, default='?')
    color_hex     = models.CharField(max_length=9,  default='#3a9aab')
    protocol      = models.CharField(max_length=8,  choices=PROTOCOL_CHOICES)
    client_id     = models.CharField(max_length=300, blank=True)
    client_secret = models.CharField(max_length=500, blank=True)
    metadata_url  = models.URLField(blank=True)
    redirect_uri  = models.URLField(blank=True)
    tenant_domain = models.CharField(max_length=100, blank=True)
    is_enabled    = models.BooleanField(default=False)
    user_count    = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'sso_providers'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.protocol})'


class SecurityPolicy(models.Model):
    """Singleton — always pk=1."""
    max_attempts         = models.PositiveSmallIntegerField(default=5)
    lockout_duration     = models.PositiveIntegerField(default=15)
    session_timeout      = models.PositiveIntegerField(default=30)
    max_sessions         = models.PositiveSmallIntegerField(default=3)
    captcha_enabled      = models.BooleanField(default=True)
    ip_restriction       = models.BooleanField(default=False)
    passwordless_enabled = models.BooleanField(default=False)
    adaptive_auth        = models.BooleanField(default=True)
    require_mfa          = models.BooleanField(default=False)
    remember_me          = models.BooleanField(default=True)
    remember_me_days     = models.PositiveSmallIntegerField(default=7)
    access_token_expiry  = models.PositiveIntegerField(default=30)
    refresh_token_expiry = models.PositiveIntegerField(default=7)
    updated_at           = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'security_policy'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class BlockedIP(models.Model):
    ip_address = models.GenericIPAddressField(unique=True)
    reason     = models.CharField(max_length=300)
    city       = models.CharField(max_length=60, blank=True)
    blocked_by = models.ForeignKey(AuthUser, null=True, blank=True,
                  on_delete=models.SET_NULL, related_name='blocked_ips')
    blocked_at = models.DateTimeField(auto_now_add=True)
    is_active  = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'blocked_ips'
        ordering = ['-blocked_at']

    def __str__(self):
        return f'{self.ip_address} — {self.reason}'
# audit/models.py
from django.db import models
from django.contrib.auth.models import User as AuthUser


class AuditLog(models.Model):
    """
    Central immutable log — every action across all modules.

    NEVER update or delete rows. Append-only.
    user FK is SET_NULL so logs survive user deletion.
    user_snapshot stores name/role at time of action — preserved forever.
    """
    ACTION_CHOICES = [
        ('login',       'Login'),
        ('logout',      'Logout'),
        ('login_fail',  'Login Failed'),
        ('create',      'Create'),
        ('update',      'Update'),
        ('delete',      'Delete'),
        ('export',      'Export'),
        ('import',      'Import'),
        ('permission',  'Permission Change'),
        ('settings',    'Settings Change'),
        ('security',    'Security Event'),
        ('view',        'View'),
        ('approve',     'Approve'),
        ('suspend',     'Suspend'),
        ('password',    'Password Reset'),
        ('mfa',         'MFA Change'),
        ('api_token',   'API Token'),
        ('sso',         'SSO Change'),
        ('temp_grant',  'Temp Access Granted'),
        ('temp_revoke', 'Temp Access Revoked'),
        ('backup',      'Backup'),
    ]

    MODULE_CHOICES = [
        ('CRM',       'CRM'),
        ('HR',        'HR'),
        ('Finance',   'Finance'),
        ('Marketing', 'Marketing'),
        ('Analytics', 'Analytics'),
        ('AI',        'AI Module'),
        ('Settings',  'Settings'),
        ('Auth',      'Auth & Security'),
        ('System',    'System'),
        ('Users',     'User Management'),
    ]

    SEVERITY_CHOICES = [
        ('low',      'Low'),
        ('medium',   'Medium'),
        ('high',     'High'),
        ('critical', 'Critical'),
    ]

    # ── Who ──
    user          = models.ForeignKey(
        AuthUser, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='audit_logs'
    )
    user_snapshot = models.JSONField(default=dict)
    # e.g. {'name': 'Ali Hassan', 'email': 'ali@crm.com', 'initials': 'AH', 'role': 'Sales Manager'}
    role_at_time  = models.CharField(max_length=80, blank=True)

    # ── What ──
    action        = models.CharField(max_length=15, choices=ACTION_CHOICES, db_index=True)
    module        = models.CharField(max_length=15, choices=MODULE_CHOICES, db_index=True)
    entity        = models.CharField(max_length=300)    # 'User: Ali Hassan'

    # ── Where ──
    ip_address    = models.GenericIPAddressField(null=True, blank=True)
    city          = models.CharField(max_length=60,  blank=True)
    device_info   = models.CharField(max_length=200, blank=True)

    # ── Diff ──
    before_data   = models.JSONField(null=True, blank=True)   # state before change
    after_data    = models.JSONField(null=True, blank=True)   # state after change

    # ── Severity & time ──
    severity      = models.CharField(
        max_length=10, choices=SEVERITY_CHOICES,
        default='low', db_index=True
    )
    timestamp     = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'audit_logs'
        ordering = ['-timestamp']
        verbose_name        = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        indexes = [
            models.Index(fields=['module', 'action']),
            models.Index(fields=['severity', 'timestamp']),
            models.Index(fields=['user', 'timestamp']),
        ]

    def __str__(self):
        return f'[{self.severity.upper()}] {self.action} — {self.module} — {self.timestamp}'

    def save(self, *args, **kwargs):
        if self.pk:
            raise PermissionError('AuditLog rows are immutable — never update.')
        # Auto-populate snapshot
        if self.user and not self.user_snapshot:
            p = getattr(self.user, 'profile', None)
            ur = self.user.user_roles.filter(is_active=True).select_related('role').first()
            self.user_snapshot = {
                'name':     p.full_name if p else self.user.get_full_name(),
                'email':    self.user.email,
                'initials': p.avatar_initials if p else '',
            }
            self.role_at_time = ur.role.name if ur else ''
        super().save(*args, **kwargs)
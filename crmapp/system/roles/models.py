# roles/models.py
from django.db import models
from django.contrib.auth.models import User as AuthUser

MODULE_CHOICES = [
    ('crm',       'CRM'),
    ('hr',        'HR'),
    ('finance',   'Finance'),
    ('marketing', 'Marketing'),
    ('analytics', 'Analytics'),
    ('ai',        'AI Module'),
    ('settings',  'Settings'),
]

ACTION_CHOICES = [
    ('view',    'View'),
    ('create',  'Create'),
    ('edit',    'Edit'),
    ('delete',  'Delete'),
    ('approve', 'Approve'),
    ('export',  'Export'),
    ('import',  'Import'),
]


class Role(models.Model):
    slug        = models.SlugField(max_length=60, unique=True)
    name        = models.CharField(max_length=80)
    description = models.TextField(blank=True)
    color_hex   = models.CharField(max_length=9, default='#3a9aab')
    level       = models.PositiveSmallIntegerField(default=5)    # 1=highest
    is_system   = models.BooleanField(default=False)    
    created_by  = models.ForeignKey(
        AuthUser, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='created_roles'
    )         # cannot be deleted
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table            = 'roles'
        ordering            = ['level', 'name']
        verbose_name        = 'Role'
        verbose_name_plural = 'Roles'

    def __str__(self):
        return self.name

    @property
    def user_count(self):
        return self.user_assignments.filter(is_active=True).count()


class Permission(models.Model):
    """49 rows: 7 modules × 7 actions."""
    module = models.CharField(max_length=20, choices=MODULE_CHOICES, db_index=True)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES, db_index=True)

    class Meta:
        db_table        = 'permissions'
        unique_together = ('module', 'action')
        ordering        = ['module', 'action']
        verbose_name        = 'Permission'
        verbose_name_plural = 'Permissions'

    def __str__(self):
        return f'{self.module}:{self.action}'


class RolePermission(models.Model):
    """Pivot: Role ↔ Permission with granted flag."""
    role       = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='permissions')
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name='role_grants')
    granted    = models.BooleanField(default=True)

    class Meta:
        db_table        = 'role_permissions'
        unique_together = ('role', 'permission')
        verbose_name        = 'Role Permission'
        verbose_name_plural = 'Role Permissions'

    def __str__(self):
        return f'{self.role.name} — {self.permission} [{"✓" if self.granted else "✗"}]'


class UserRole(models.Model):
    user        = models.ForeignKey(AuthUser, on_delete=models.CASCADE, related_name='user_roles')
    role        = models.ForeignKey(Role, on_delete=models.CASCADE,   related_name='user_assignments')  # ← PROTECT → CASCADE
    assigned_by = models.ForeignKey(
        AuthUser, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='roles_assigned'
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    is_active   = models.BooleanField(default=True)

    class Meta:
        db_table        = 'user_roles'
        unique_together = ('user', 'role')
        ordering        = ['-assigned_at']
        verbose_name        = 'User Role'
        verbose_name_plural = 'User Roles'

    def __str__(self):
        p = getattr(self.user, 'profile', None)
        name = p.full_name if p else self.user.email
        return f'{name} → {self.role.name}'


class TemporaryAccess(models.Model):
    """Time-limited role grant — Temp Access tab."""
    user       = models.ForeignKey(AuthUser, on_delete=models.CASCADE, related_name='temp_access')
    role       = models.ForeignKey(Role,     on_delete=models.PROTECT,  related_name='temp_grants')
    reason     = models.CharField(max_length=200)
    granted_by = models.ForeignKey(
        AuthUser, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='temp_access_granted'
    )
    granted_at = models.DateField(auto_now_add=True)
    expires_at = models.DateField()
    is_active  = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table            = 'temporary_access'
        ordering            = ['expires_at']
        verbose_name        = 'Temporary Access'
        verbose_name_plural = 'Temporary Access Grants'

    def __str__(self):
        p = getattr(self.user, 'profile', None)
        name = p.full_name if p else self.user.email
        return f'{name} → {self.role.name} until {self.expires_at}'
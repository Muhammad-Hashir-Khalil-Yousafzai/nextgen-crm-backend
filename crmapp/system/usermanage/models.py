# usermanage/models.py
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User as AuthUser


# ──────────────────────────────────────────────
# DEPARTMENT
# ──────────────────────────────────────────────
class Department(models.Model):
    slug      = models.SlugField(max_length=60, unique=True)
    name      = models.CharField(max_length=80)
    color_hex = models.CharField(max_length=9, default='#3a9aab')

    head = models.ForeignKey(
        AuthUser,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='headed_departments'
    )

    size = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'departments'
        ordering = ['name']
        verbose_name = 'Department'
        verbose_name_plural = 'Departments'

    def __str__(self):
        return self.name


# ──────────────────────────────────────────────
# USER PROFILE
# ──────────────────────────────────────────────
class UserProfile(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
        ('deleted', 'Deleted'),
    ]

    user = models.OneToOneField(
        AuthUser,
        on_delete=models.CASCADE,
        related_name='profile'
    )

    # ✅ NEW — tracks which superadmin created this user (tenant link)
    created_by = models.ForeignKey(
        AuthUser,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='created_users'
    )

    full_name       = models.CharField(max_length=100, blank=True)
    phone           = models.CharField(max_length=25, blank=True)
    avatar_initials = models.CharField(max_length=4, blank=True)
    city            = models.CharField(max_length=60, blank=True)

    status = models.CharField(
        max_length=12,
        choices=STATUS_CHOICES,
        default='active',
        db_index=True
    )

    department = models.ForeignKey(
        Department,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='users'
    )

    login_count  = models.PositiveIntegerField(default=0)
    action_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'users'
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return self.full_name or self.user.email

    def save(self, *args, **kwargs):
        if self.pk:
            try:
                old_instance = UserProfile.objects.get(pk=self.pk)
                self._old_department_id = old_instance.department_id
            except UserProfile.DoesNotExist:
                self._old_department_id = None
        else:
            self._old_department_id = None

        if not self.avatar_initials and self.full_name:
            parts = self.full_name.strip().split()
            self.avatar_initials = ''.join(p[0] for p in parts[:2]).upper()

        super().save(*args, **kwargs)

        if self.pk and self.user_id:
            AuthUser.objects.filter(pk=self.user_id).update(
                is_active=(self.status == 'active')
            )

    # ──────────────────────────────────────────
    # PROPERTIES
    # ──────────────────────────────────────────
    @property
    def email(self):
        return self.user.email

    @property
    def date_joined(self):
        return self.user.date_joined

    @property
    def last_login(self):
        return self.user.last_login

    @property
    def is_active(self):
        return self.status == 'active'

    # ✅ NEW — helper to get the tenant owner (superadmin)
    @property
    def tenant_owner(self):
        """Returns the superadmin who owns this user's tenant"""
        if self.user.is_superuser:
            return self.user
        return self.created_by


# ──────────────────────────────────────────────
# USER SESSION
# ──────────────────────────────────────────────
class UserSession(models.Model):
    user = models.ForeignKey(
        AuthUser,
        on_delete=models.CASCADE,
        related_name='sessions'
    )

    ip_address    = models.GenericIPAddressField()
    city          = models.CharField(max_length=60, blank=True)
    device_info   = models.CharField(max_length=200, blank=True)
    session_key   = models.CharField(max_length=64, unique=True)

    is_active     = models.BooleanField(default=True, db_index=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    expires_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'user_sessions'
        ordering = ['-last_activity']

    def __str__(self):
        name = getattr(self.user, 'profile', None)
        name = name.full_name if name else self.user.email
        return f'{name} — {self.ip_address}'


# ──────────────────────────────────────────────
# USER ACTIVITY LOG
# ──────────────────────────────────────────────
class UserActivityLog(models.Model):
    ACTION_CHOICES = [
        ('create', 'User Created'),
        ('update', 'User Updated'),
        ('role', 'Role Updated'),
        ('suspend', 'User Suspended'),
        ('activate', 'User Activated'),
        ('delete', 'User Deleted'),
        ('import', 'Bulk Import'),
        ('export', 'Export'),
        ('security', 'Security Action'),
        ('password', 'Password Reset'),
        ('mfa', 'MFA Changed'),
        ('dept', 'Department Updated'),
    ]

    actor = models.ForeignKey(
        AuthUser,
        null=True,
        on_delete=models.SET_NULL,
        related_name='actions_performed'
    )

    target_user = models.ForeignKey(
        AuthUser,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='activity_received'
    )

    action      = models.CharField(max_length=20, choices=ACTION_CHOICES, db_index=True)
    description = models.CharField(max_length=300)
    timestamp   = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'user_activity_logs'
        ordering = ['-timestamp']

    def __str__(self):
        return f'{self.actor} — {self.action}'


# ──────────────────────────────────────────────
# SIGNALS (Auto-Create UserProfile)
# ──────────────────────────────────────────────
@receiver(post_save, sender=AuthUser)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)
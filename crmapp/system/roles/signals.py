# roles/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import RolePermission, UserRole
from .permissions import invalidate_perm_cache


@receiver(post_save, sender=RolePermission)
def invalidate_on_perm_change(sender, instance, **kwargs):
    from django.contrib.auth.models import User as AuthUser
    user_ids = instance.role.user_assignments.filter(
        is_active=True
    ).values_list('user_id', flat=True)
    for u in AuthUser.objects.filter(pk__in=user_ids):
        invalidate_perm_cache(u)


@receiver(post_save, sender=UserRole)
@receiver(post_delete, sender=UserRole)
def invalidate_on_role_change(sender, instance, **kwargs):
    invalidate_perm_cache(instance.user)
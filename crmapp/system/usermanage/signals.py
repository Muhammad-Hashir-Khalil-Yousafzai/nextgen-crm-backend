# usermanage/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User as AuthUser
from .models import UserProfile


@receiver(post_save, sender=AuthUser)
def create_user_profile(sender, instance, created, **kwargs):
    """Auto-create UserProfile row for every new auth_user."""
    if created:
        UserProfile.objects.get_or_create(
            user=instance,
            defaults={'full_name': f'{instance.first_name} {instance.last_name}'.strip()}
        )


@receiver(post_save, sender=AuthUser)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        if not instance.is_active and instance.profile.status == 'active':
            UserProfile.objects.filter(pk=instance.profile.pk).update(status='inactive')
        elif instance.is_active and instance.profile.status == 'inactive':
            UserProfile.objects.filter(pk=instance.profile.pk).update(status='active')
@receiver(post_save, sender=UserProfile)
def update_department_size_on_save(sender, instance, created, **kwargs):
    """
    Recalculate department.size when profile changes department.
    Also handle when a new profile is created with a department.
    """
    if instance.department:
        _update_dept_size(instance.department)
    
    # If department was changed from old to new, we need to update old department too
    if not created and hasattr(instance, '_old_department_id'):
        if instance._old_department_id and instance._old_department_id != instance.department_id:
            from .models import Department
            try:
                old_dept = Department.objects.get(pk=instance._old_department_id)
                _update_dept_size(old_dept)
            except Department.DoesNotExist:
                pass


@receiver(post_delete, sender=UserProfile)
def update_department_size_on_delete(sender, instance, **kwargs):
    """Update department size when a profile is deleted."""
    if instance.department:
        _update_dept_size(instance.department)


def _update_dept_size(dept):
    """Helper function to update department size."""
    from .models import Department
    # Use a fresh queryset to get accurate count
    dept.size = Department.objects.get(pk=dept.pk).users.count()
    dept.save(update_fields=['size'])
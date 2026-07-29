# auth_security/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User as AuthUser
from .models import MFAUser


@receiver(post_save, sender=AuthUser)
def create_mfa_record(sender, instance, created, **kwargs):
    """Auto-create MFAUser (disabled) for every new auth_user."""
    if created:
        MFAUser.objects.get_or_create(user=instance)
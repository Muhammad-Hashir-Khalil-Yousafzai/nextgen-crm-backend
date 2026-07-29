"""
FollowUp create hone par contact ko turant email bhejta hai.
"""
import logging
import traceback

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings

from .models import FollowUp

logger = logging.getLogger('crmapp')


def _get_contact_email(followup: FollowUp):
    """
    Contact se email nikalta hai. Contact model ka field name
    'email' assume kiya hai — agar alag hai to yahan update karna.
    """
    contact = getattr(followup, 'contact', None)
    if not contact:
        return None
    return getattr(contact, 'email', None)


def _get_contact_name(followup: FollowUp):
    contact = getattr(followup, 'contact', None)
    if not contact:
        return 'there'
    # contact_name property already model/serializer mein hai
    name = getattr(followup, 'contact_name', None)
    return name or getattr(contact, 'name', 'there')


@receiver(post_save, sender=FollowUp)
def send_followup_created_email(sender, instance: FollowUp, created, **kwargs):
    """
    Sirf jab FollowUp naya create ho (created=True) tab hi email jaye.
    Update pe dobara email nahi jani chahiye.
    """
    if not created:
        return

    email = _get_contact_email(instance)
    if not email:
        logger.info(
            f"[FollowUp Email] Skip — FollowUp id={instance.id} ka contact/email nahi mila."
        )
        return

    contact_name = _get_contact_name(instance)
    due_date = instance.due_date.strftime('%d %b %Y') if instance.due_date else 'N/A'

    subject = f"Follow-up Scheduled: {instance.title}"
    message = (
        f"Hi {contact_name},\n\n"
        f"Aapke liye ek follow-up schedule hua hai:\n\n"
        f"Title: {instance.title}\n"
        f"Description: {instance.description or '-'}\n"
        f"Due Date: {due_date}\n"
        f"Priority: {instance.priority}\n\n"
        f"Thank you,\n"
        f"NextGen CRM Team"
    )

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        logger.info(f"[FollowUp Email] Sent to {email} for FollowUp id={instance.id}")
    except Exception:
        logger.error(
            f"[FollowUp Email] FAILED for FollowUp id={instance.id}\n{traceback.format_exc()}"
        )
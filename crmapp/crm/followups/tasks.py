"""
Celery tasks — Recurring follow-ups ke liye scheduled emails.
"""
import logging
import traceback
from datetime import timedelta

from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

from .models import FollowUp

logger = logging.getLogger('crmapp')

# recurring_frequency string → timedelta mapping
FREQUENCY_MAP = {
    'daily':   timedelta(days=1),
    'weekly':  timedelta(weeks=1),
    'monthly': timedelta(days=30),
}


@shared_task(name='crmapp.crm.followups.tasks.process_recurring_followups')
def process_recurring_followups():
    """
    Har baar chalne par check karta hai:
    - recurring_enabled=True wale follow-ups
    - jinki due_date (ya last email date) + frequency interval guzar chuki hai
    Unhe email bhejta hai aur agli due_date automatically aage badha deta hai.
    """
    now = timezone.now()
    recurring_followups = FollowUp.objects.filter(recurring_enabled=True)

    sent_count = 0

    for fu in recurring_followups:
        frequency = fu.recurring_frequency or 'weekly'
        interval = fu.recurring_interval or 1
        delta = FREQUENCY_MAP.get(frequency, timedelta(weeks=1)) * interval

        if not fu.due_date:
            continue

        # Agar due_date guzar chuki hai to email bhejo
        if fu.due_date <= now:
            email = getattr(getattr(fu, 'contact', None), 'email', None)

            if email:
                try:
                    send_mail(
                        subject=f"Recurring Follow-up Reminder: {fu.title}",
                        message=(
                            f"Hi,\n\n"
                            f"Ye ek recurring follow-up reminder hai:\n\n"
                            f"Title: {fu.title}\n"
                            f"Description: {fu.description or '-'}\n\n"
                            f"Thank you,\n"
                            f"NextGen CRM Team"
                        ),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[email],
                        fail_silently=False,
                    )
                    sent_count += 1
                    logger.info(f"[Recurring FollowUp] Email sent to {email} (FollowUp id={fu.id})")
                except Exception:
                    logger.error(
                        f"[Recurring FollowUp] FAILED id={fu.id}\n{traceback.format_exc()}"
                    )
                    continue
            else:
                logger.info(f"[Recurring FollowUp] Skip id={fu.id} — email nahi mila.")

            # Chahe email gayi ho ya na gayi ho (no email case), next due_date aage badhao
            fu.due_date = fu.due_date + delta
            fu.save(update_fields=['due_date'])

    logger.info(f"[Recurring FollowUp] Task complete — {sent_count} emails sent.")
    return f"{sent_count} recurring emails sent"
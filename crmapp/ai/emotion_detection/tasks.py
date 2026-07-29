import requests
from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import GmailConnection, EmotionDetection, AlertLog
from .services.gmail_service import fetch_unread_emails
from .services.emotion_service import classify_emotion
from .views import _evaluate_alert_rules


@shared_task(bind=True, max_retries=3)
def poll_all_gmail_inboxes(self):
    """
    Celery beat task — runs on schedule.
    Loops every active GmailConnection (could be multiple per business)
    and processes unread emails for each independently.

    One broken/expired connection no longer blocks the others — it gets
    logged, deactivated if the token is dead, and the loop continues to
    the next inbox instead of aborting the whole batch.
    """
    connections = GmailConnection.objects.filter(is_active=True)
    print(f"[tasks] Polling {connections.count()} Gmail inbox(es)")

    for connection in connections:
        try:
            _process_connection(connection)
        except Exception as exc:
            print(f"[tasks] Failed for {connection.gmail_address}: {exc}")
            if "invalid_grant" in str(exc) or "Token has been expired" in str(exc):
                connection.is_active = False
                connection.save(update_fields=["is_active"])
                print(f"[tasks] Deactivated {connection.gmail_address} — token expired, needs re-auth")
            continue  # move to next connection instead of aborting the whole task


def _process_connection(connection: GmailConnection):
    """Fetch + classify emails for one GmailConnection."""
    emails  = fetch_unread_emails(connection)
    created = 0

    for em in emails:
        result = classify_emotion(em["full_text"])

        detection, is_new = EmotionDetection.objects.get_or_create(
            gmail_message_id = em["gmail_message_id"],
            defaults = {
                "user":             connection.user,
                "gmail_connection": connection,
                "customer_name":    em["customer_name"],
                "customer_email":   em["customer_email"],
                "email_subject":    em["subject"],
                "email_body_snippet": em["body_snippet"],
                "emotion":          result["emotion"],
                "intensity":        result["intensity"],
                "confidence":       result["confidence"],
            }
        )

        if not is_new:
            continue

        _evaluate_alert_rules(connection.user, detection)
        _trigger_lead_workflow(em)
        created += 1

    connection.last_synced_at = timezone.now()
    connection.save(update_fields=["last_synced_at"])

    print(f"[tasks] {connection.gmail_address} → {created} new emails classified")


def _trigger_lead_workflow(em: dict):
    sender_email = em.get("customer_email", "")
    local_part = sender_email.split("@")[0].lower() if "@" in sender_email else ""
    NOREPLY_MARKERS = ("noreply", "no-reply", "notifications", "notification", "digest", "updates", "marketing")

    if not sender_email or any(marker in local_part for marker in NOREPLY_MARKERS):
        print(f"[tasks] Skipping likely non-lead sender: {sender_email}")
        return

    webhook_url = getattr(
        settings,
        "EMAIL_TO_LEAD_WEBHOOK_URL",
        "http://localhost:8000/api/automation/workflows/webhooks/2b69987f90aa45fdb0408cf5d2037a0e/",
    )
    payload = {
        "sender_name":  em.get("customer_name", "") or "Unknown",
        "sender_email": sender_email,
        "sender_phone": "",
    }
    try:
        resp = requests.post(webhook_url, json=payload, timeout=15)
        resp.raise_for_status()
        print(f"[tasks] Lead workflow triggered for {sender_email}: {resp.json()}")
    except requests.RequestException as exc:
        print(f"[tasks] Lead workflow trigger failed for {sender_email}: {exc}")
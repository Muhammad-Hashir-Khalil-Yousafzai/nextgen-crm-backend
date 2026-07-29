"""
crmapp/ai/recommendation/tasks.py

Celery tasks for the Recommendation Engine.

Schedule (add to settings.CELERY_BEAT_SCHEDULE):

    "rec-proactive-scan": {
        "task":     "crmapp.ai.recommendation.tasks.run_proactive_scan",
        "schedule": crontab(minute="*/30"),   # every 30 minutes
    },
    "rec-build-all-profiles": {
        "task":     "crmapp.ai.recommendation.tasks.build_all_profiles",
        "schedule": crontab(hour=2, minute=0),   # nightly at 2am
    },
    "rec-channel-snapshot": {
        "task":     "crmapp.ai.recommendation.tasks.snapshot_channels",
        "schedule": crontab(hour=1, minute=0),   # nightly at 1am
    },
    "rec-model-snapshot": {
        "task":     "crmapp.ai.recommendation.tasks.snapshot_model_perf",
        "schedule": crontab(day_of_month=1, hour=3, minute=0),  # monthly
    },
"""

import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="crmapp.ai.recommendation.tasks.run_proactive_scan")
def run_proactive_scan():
    """
    Scans all CRM + XAI + Emotion signals and fires ProactiveAlerts.
    Runs every 30 minutes.
    Idempotent — skips leads already alerted within 24h.
    """
    from .services import check_proactive_signals
    try:
        fired = check_proactive_signals()
        logger.info(f"[REC TASK] Proactive scan complete — {fired} alerts fired")
        return {"fired": fired}
    except Exception as e:
        logger.error(f"[REC TASK] Proactive scan failed: {e}")
        raise


@shared_task(name="crmapp.ai.recommendation.tasks.build_all_profiles")
def build_all_profiles():
    """
    Rebuilds UserProfile for every Lead nightly.
    Respects rate — processes in batches of 100 with small delays.
    """
    from .services import build_user_profile
    from crmapp.crm.leads.models import Lead
    import time

    leads   = Lead.objects.values_list("id", flat=True)
    total   = len(leads)
    success = 0
    errors  = 0

    for i, lead_id in enumerate(leads):
        try:
            build_user_profile("lead", str(lead_id))
            success += 1
        except Exception as e:
            logger.warning(f"[REC TASK] Profile build failed for lead {lead_id}: {e}")
            errors += 1

        # Avoid hammering DB: small sleep every 100 records
        if i > 0 and i % 100 == 0:
            time.sleep(0.5)

    logger.info(f"[REC TASK] Profile build complete — {success} ok, {errors} failed (total {total})")
    return {"total": total, "success": success, "errors": errors}


@shared_task(name="crmapp.ai.recommendation.tasks.generate_all_recommendations")
def generate_all_recommendations():
    """
    Generates fresh recommendations for all profiles.
    Called after build_all_profiles (chain them if needed).
    Skips profiles that already have pending recommendations from today.
    """
    from .services import generate_recommendations
    from .models import UserProfile, RecommendationItem
    from django.utils import timezone

    today    = timezone.now().date()
    profiles = UserProfile.objects.all()
    total    = 0

    for profile in profiles:
        already_has = RecommendationItem.objects.filter(
            profile=profile,
            status="pending",
            created_at__date=today,
        ).exists()
        if already_has:
            continue
        try:
            recs = generate_recommendations(profile)
            total += len(recs)
        except Exception as e:
            logger.warning(f"[REC TASK] generate_recommendations failed for {profile.subject_name}: {e}")

    logger.info(f"[REC TASK] Generated {total} recommendations across all profiles")
    return {"total": total}


@shared_task(name="crmapp.ai.recommendation.tasks.snapshot_channels")
def snapshot_channels():
    """Daily channel performance snapshot. Runs at 1am."""
    from .services import snapshot_channel_performance
    try:
        snapshot_channel_performance()
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"[REC TASK] Channel snapshot failed: {e}")
        raise


@shared_task(name="crmapp.ai.recommendation.tasks.snapshot_model_perf")
def snapshot_model_perf():
    """Monthly model performance snapshot. Runs on 1st of each month."""
    from .services import snapshot_model_performance
    try:
        snapshot_model_performance()
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"[REC TASK] Model perf snapshot failed: {e}")
        raise


@shared_task(name="crmapp.ai.recommendation.tasks.expire_old_recommendations")
def expire_old_recommendations():
    """
    Marks recommendations older than 7 days as expired if still pending.
    Keeps the recommendation table clean.
    """
    from .models import RecommendationItem
    from django.utils import timezone

    cutoff  = timezone.now() - __import__("datetime").timedelta(days=7)
    expired = RecommendationItem.objects.filter(
        status="pending",
        created_at__lte=cutoff,
    ).update(status="expired")

    logger.info(f"[REC TASK] Expired {expired} old pending recommendations")
    return {"expired": expired}
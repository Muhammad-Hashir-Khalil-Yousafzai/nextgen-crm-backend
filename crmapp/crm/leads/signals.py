"""
signals.py
──────────
Lead Automation — Jab bhi naya Lead bane, yeh sab auto hoga:

    1.  AI Score lagao (analytics module se)
    2.  Lead classify karo (hot / warm / cold)
    3.  Smart assignment (senior / least-busy / round-robin)
    4.  Priority compute karo
    5.  Auto FollowUp create karo
    6.  Trigger workflow builder (email/WhatsApp/Slack — condition-based, see Workflow Builder)
    7.  Activity log update karo
    8.  Lead → Contact conversion (jab Closed Won ho)
    9.  XAI prediction + explanation (SHAP + LIME + Groq)

NOTE: Direct email/WhatsApp sending (_send_email, _send_whatsapp below) has been
disabled here. Notifications are now owned by the Workflow Builder's condition
nodes (see /workflows/ — "EMAIL on CRM" and similar), so a lead only ever gets
ONE notification instead of two. The functions are kept below, unused, in case
you need to roll back.
"""

import logging
from django.db.models.signals import post_save
from django.dispatch           import receiver
from django.core.mail          import send_mail
from django.conf               import settings
from django.utils              import timezone
from datetime                  import timedelta
import requests

from .models     import Lead
from .assignment import assign_lead, compute_priority, get_followup_hours, classify_lead

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL 1 — Naya Lead bane tab
# ─────────────────────────────────────────────────────────────────────────────
@receiver(post_save, sender=Lead)
def on_lead_saved(sender, instance, created, **kwargs):
    """
    created=True  → naya lead — poora automation chalao
    created=False → update — sirf conversion check karo
    """

    # ── NAYA LEAD ─────────────────────────────────────────────────
    if created:
        logger.info(f"[Signal] New lead — ID:{instance.pk} | Name:{instance.name}")

        # Step 1 — AI Score
        score = _compute_ai_score(instance)

        # Step 2 — Classify + Priority
        priority  = compute_priority(score, instance.value)
        lead_type = classify_lead(score)

        # Step 3 — Auto Assign
        agent = instance.assigned_to if instance.assigned_to else assign_lead(instance)

        # DB update
        Lead.objects.filter(pk=instance.pk).update(
            score       = score,
            priority    = priority,
            assigned_to = agent,
        )
        instance.score       = score
        instance.priority    = priority
        instance.assigned_to = agent

        logger.info(f"[Signal] Score:{score} | Type:{lead_type} | Priority:{priority} | Agent:{agent}")

        # Step 4 — Auto FollowUp
        _create_followup(instance)

        # Step 5 — Trigger workflow builder (handles email/WhatsApp/Slack via condition nodes)
        _trigger_workflow(instance)

        # Step 6 — Activity log
        _log_activity(instance)

        # Step 9 — XAI Prediction + Explanation
        _run_xai(instance)

        logger.info(f"[Signal] Automation complete for Lead ID:{instance.pk}")

    # ── EXISTING LEAD UPDATE ───────────────────────────────────────
    else:
        # Step 8 — Closed Won → Auto Contact banao
        if instance.status == 'closed':
            _convert_lead_to_contact(instance)


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — AI SCORE
# ─────────────────────────────────────────────────────────────────────────────
def _compute_ai_score(lead):
    """
    Brand-new leads always have notes_count=0 and activities=0 at creation
    time — but the ML model was trained on those as features, so it reads
    "0 notes, 0 activities" as a strong signal the lead will be lost
    (since that pattern dominates the 'lost' class in training data).
    This makes every fresh lead score near 0 regardless of source/value.

    Fix: use rule-based scoring for leads with no activity yet.
    Once a lead has real notes/activities logged, hand off to the ML model.
    """
    if (lead.notes_count or 0) == 0 and (lead.activities or 0) == 0:
        logger.info("[Signal] New lead with no activity yet — using rule-based score")
    else:
        try:
            from crmapp.analytics.ai.lead_scoring import predict
            score = predict(lead)
            logger.info(f"[Signal] AI Score (ML): {score}")
            return int(score)
        except Exception as e:
            logger.warning(f"[Signal] AI scoring unavailable ({e}) — using rule-based")

    score = 0
    source_scores = {
        'Referral': 30, 'Website': 20, 'LinkedIn': 20,
        'Event': 15, 'Cold Call': 10, 'Other': 5,
    }
    score += source_scores.get(lead.source, 5)

    value = float(lead.value or 0)
    if value >= 10000:   score += 30
    elif value >= 5000:  score += 20
    elif value >= 1000:  score += 10

    if lead.email:        score += 10
    if lead.phone:        score += 10
    if lead.company_name or lead.company_id: score += 10

    score += int((lead.probability or 50) * 0.1)
    final = min(score, 100)
    logger.info(f"[Signal] AI Score (rule-based): {final}")
    return final
# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — AUTO FOLLOWUP
# ─────────────────────────────────────────────────────────────────────────────
def _create_followup(lead):
    try:
        from crmapp.crm.followups.models import FollowUp

        hours     = get_followup_hours(lead.priority)
        lead_type = classify_lead(lead.score)
        due       = timezone.now() + timedelta(hours=hours)

        FollowUp.objects.create(
            title       = f'Initial {lead_type.upper()} Lead call — {lead.name}',
            description = (
                f'Auto-created follow-up.\n'
                f'Source: {lead.source} | Score: {lead.score} | '
                f'Priority: {lead.priority} | Value: ${lead.value}'
            ),
            type        = 'call',
            priority    = lead.priority,
            status      = 'pending',
            due_date    = due,
            assigned_to = lead.assigned_to or 'Unassigned',
            notes       = f'Lead ID: {lead.pk} | Company: {lead.company_name}',
            contact     = lead.contact,
        )
        logger.info(f"[Signal] FollowUp created — due in {hours}h at {due}")

    except ImportError:
        logger.warning("[Signal] FollowUp model not found — skipping")
    except Exception as e:
        logger.error(f"[Signal] FollowUp creation failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 5 — TRIGGER WORKFLOW BUILDER (replaces direct email/WhatsApp send)
# ─────────────────────────────────────────────────────────────────────────────
def _trigger_workflow(lead):
    """
    Fires every workflow marked trigger_on_lead_created=True.
    No settings.py editing needed — toggle this in the Workflow Builder UI instead.
    """
    from crmapp.automation.workflows.models import Workflow, WorkflowWebhook

    active_workflows = Workflow.objects.filter(trigger_on_lead_created=True)

    if not active_workflows.exists():
        logger.warning("[Signal] No workflow marked trigger_on_lead_created — skipping")
        return

    payload = {
        "lead_name":  lead.name,
        "lead_email": lead.email,
        "lead_id":    str(lead.pk),
        "phone":      lead.phone or "",
        "company":    lead.company_name or "",
        "priority":   lead.priority,
        "score":      lead.score,
        "source":     lead.source,
        "agent":      lead.assigned_to or "",
    }

    for wf in active_workflows:
        webhook = WorkflowWebhook.objects.filter(workflow=wf, is_active=True).first()
        if not webhook:
            logger.warning(f"[Signal] Workflow '{wf.name}' has no active webhook — skipping")
            continue

        url = f"http://localhost:8000/api/automation/workflows/webhooks/{webhook.secret}/"
        try:
            resp = requests.post(url, json=payload, timeout=5)
            resp.raise_for_status()
            logger.info(f"[Signal] Workflow '{wf.name}' triggered for Lead {lead.pk}: {resp.json()}")
        except requests.RequestException as exc:
            logger.error(f"[Signal] Workflow '{wf.name}' trigger failed for Lead {lead.pk}: {exc}")
# ─────────────────────────────────────────────────────────────────────────────
# [UNUSED — kept for rollback] STEP 5 (OLD) — AUTO EMAIL
# ─────────────────────────────────────────────────────────────────────────────
def _send_email(lead):
    if not lead.email:
        logger.info("[Signal] No email — skipping email")
        return

    try:
        subject = f'Thank you for your inquiry, {lead.name}!'
        message = f"""Assalam o Alaikum {lead.name},

Thank you for reaching out to us!

We have received your inquiry and our team will contact you shortly.

📋 Your Details:
━━━━━━━━━━━━━━━━━━━━━━━━
Reference ID   : LEAD-{lead.pk}
Assigned Agent : {lead.assigned_to}
Priority       : {lead.priority.upper()}
━━━━━━━━━━━━━━━━━━━━━━━━

Our team will follow up with you within:
- High Priority  → 2 hours
- Medium Priority → 24 hours
- Low Priority   → 48 hours

Best regards,
NextGen CRM Team
"""
        send_mail(
            subject        = subject,
            message        = message,
            from_email     = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@nextgencrm.com'),
            recipient_list = [lead.email],
            fail_silently  = True,
        )
        logger.info(f"[Signal] Email sent → {lead.email}")
    except Exception as e:
        logger.error(f"[Signal] Email failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# [UNUSED — kept for rollback] STEP 6 (OLD) — AUTO WHATSAPP
# ─────────────────────────────────────────────────────────────────────────────
def _send_whatsapp(lead):
    if not lead.phone:
        logger.info("[Signal] No phone — skipping WhatsApp")
        return

    phone_id = getattr(settings, 'WHATSAPP_PHONE_ID', None)
    token    = getattr(settings, 'WHATSAPP_ACCESS_TOKEN', None)

    if not phone_id or not token:
        logger.warning("[Signal] WhatsApp credentials missing — skipping")
        return

    try:
        phone = ''.join(filter(str.isdigit, lead.phone))
        if phone.startswith('0'):
            phone = '92' + phone[1:]
        elif not phone.startswith('92'):
            phone = '92' + phone

        urgency_msg = {
            'high':   'Aapki inquiry bohot important hai — hum 2 ghante mein contact karenge! ⚡',
            'medium': 'Hamari team 24 ghante mein aap se rabta karegi.',
            'low':    'Hamari team jald aap se rabta karegi.',
        }.get(lead.priority, 'Hamari team jald aap se rabta karegi.')

        message_body = (
            f"Assalam o Alaikum {lead.name}! 👋\n\n"
            f"*NextGen CRM* mein aapki inquiry receive ho gayi.\n\n"
            f"📋 *Details:*\n"
            f"• Reference: LEAD-{lead.pk}\n"
            f"• Agent: {lead.assigned_to}\n\n"
            f"ℹ️ {urgency_msg}\n\n"
            f"Shukriya! 🙏"
        )

        url     = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to":   phone,
            "type": "text",
            "text": {"body": message_body},
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
        }

        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        logger.info(f"[Signal] WhatsApp → {phone} | Status: {resp.status_code}")

        if resp.status_code != 200:
            logger.warning(f"[Signal] WhatsApp response: {resp.text}")

    except Exception as e:
        logger.error(f"[Signal] WhatsApp failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 6 — ACTIVITY LOG
# ─────────────────────────────────────────────────────────────────────────────
def _log_activity(lead):
    try:
        lead_type = classify_lead(lead.score)
        new_entry = {
            'type':        'system',
            'description': (
                f'Lead auto-processed: Score={lead.score} ({lead_type.upper()}), '
                f'Assigned={lead.assigned_to}, Priority={lead.priority}'
            ),
            'time': timezone.now().isoformat(),
            'user': 'System (Auto)',
        }
        db_lead = Lead.objects.get(pk=lead.pk)
        log     = db_lead.activity_log or []
        log.insert(0, new_entry)
        Lead.objects.filter(pk=lead.pk).update(
            activity_log = log,
            activities   = db_lead.activities + 1,
        )
        logger.info(f"[Signal] Activity log updated for Lead ID:{lead.pk}")
    except Exception as e:
        logger.error(f"[Signal] Activity log failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 9 — XAI PREDICTION + EXPLANATION
# ─────────────────────────────────────────────────────────────────────────────
def _run_xai(lead):
    try:
        from crmapp.ai.xai.services import (
            predict_and_explain_lead,
            generate_counterfactuals,
            compute_global_importance,
        )
        from crmapp.ai.xai.models import MLModel

        # Re-fetch lead so score/priority updates from Step 1-3 are included
        lead = Lead.objects.get(pk=lead.pk)

        pred, expl = predict_and_explain_lead(lead, initiated_by="Auto")

        if pred.outcome_type == "negative":
            generate_counterfactuals(pred, num_cfs=3)

        ml_model = MLModel.objects.get(name="Lead Conversion Predictor")
        compute_global_importance(ml_model)

        logger.info(
            f"[Signal] XAI complete for Lead ID:{lead.pk} — "
            f"{pred.prediction_label} ({pred.confidence_score:.0%}) | "
            f"{expl.feature_contributions.count()} features"
        )
    except Exception as e:
        logger.warning(f"[Signal] XAI failed for lead {lead.pk}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 8 — LEAD TO CONTACT CONVERSION (Closed Won)
# ─────────────────────────────────────────────────────────────────────────────
def _convert_lead_to_contact(lead):
    if lead.contact_id:
        logger.info(f"[Signal] Lead ID:{lead.pk} already has contact — skipping conversion")
        return

    try:
        logger.info(f"[Signal] 🎉 Converting Lead ID:{lead.pk} ({lead.name}) to Contact...")

        company_obj = None
        try:
            from crmapp.crm.companies.models import Company

            company_name = lead.company_name or f"{lead.name}'s Company"
            company_obj  = Company.objects.filter(
                name__iexact = company_name,
                created_by   = lead.created_by,
            ).first()

            if not company_obj:
                company_obj = Company.objects.create(
                    name       = company_name,
                    industry   = 'Unknown',
                    created_by = lead.created_by,
                )
                logger.info(f"[Signal] Company created: {company_obj.name} (ID:{company_obj.pk})")
            else:
                logger.info(f"[Signal] Company found: {company_obj.name} (ID:{company_obj.pk})")

        except Exception as e:
            logger.warning(f"[Signal] Company creation failed: {e}")

        try:
            from crmapp.crm.contacts.models import Contact

            existing_contact = None
            if lead.email:
                existing_contact = Contact.objects.filter(
                    email__iexact = lead.email,
                    created_by    = lead.created_by,
                ).first()

            if existing_contact:
                contact_obj = existing_contact
                logger.info(f"[Signal] Contact already exists: {contact_obj} (ID:{contact_obj.pk})")
            else:
                name_parts = lead.name.strip().split(' ', 1)
                first_name = name_parts[0]
                last_name  = name_parts[1] if len(name_parts) > 1 else ''

                contact_obj = Contact.objects.create(
                    first_name   = first_name,
                    last_name    = last_name,
                    email        = lead.email        or '',
                    phone        = lead.phone        or '',
                    company      = company_obj,
                    source       = lead.source       or 'Website',
                    notes        = f'Converted from Lead ID:{lead.pk}. {lead.notes or ""}',
                    created_by   = lead.created_by,
                )
                logger.info(f"[Signal] ✅ Contact created: {contact_obj} (ID:{contact_obj.pk})")

            Lead.objects.filter(pk=lead.pk).update(contact=contact_obj)
            logger.info(f"[Signal] Lead ID:{lead.pk} linked to Contact ID:{contact_obj.pk}")

            db_lead = Lead.objects.get(pk=lead.pk)
            log     = db_lead.activity_log or []
            log.insert(0, {
                'type':        'conversion',
                'description': f'Lead converted to Contact (ID:{contact_obj.pk}) — {lead.name}',
                'time':        timezone.now().isoformat(),
                'user':        'System (Auto)',
            })
            Lead.objects.filter(pk=lead.pk).update(
                activity_log = log,
                activities   = db_lead.activities + 1,
            )
            logger.info(f"[Signal] 🎉 Lead to Contact conversion complete!")

        except Exception as e:
            logger.error(f"[Signal] Contact creation failed: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"[Signal] Conversion failed: {e}", exc_info=True)
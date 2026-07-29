"""
webhook_views.py
────────────────
Multi-tenant support:
  - Har organization ka alag user_id URL mein pass karo
  - /api/crm/leads/webhook/google-form/?user_id=26
  - user_id nahi diya to superadmin use hoga
"""

import json
import logging
from django.http                  import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth          import get_user_model

logger = logging.getLogger(__name__)

VERIFY_TOKEN = 'nextgencrm_verify_2024'


# ─────────────────────────────────────────────────────────────────────────────
# HELPER — User lo (multi-tenant support)
# ─────────────────────────────────────────────────────────────────────────────
def _get_user(user_id=None):
    """
    user_id diya → us user ko lo
    user_id nahi diya → superadmin lo
    
    Usage:
      Org 25: /webhook/google-form/?user_id=25
      Org 26: /webhook/google-form/?user_id=26
    """
    User = get_user_model()

    if user_id:
        user = User.objects.filter(id=user_id, is_active=True).first()
        if user:
            logger.info(f"[Webhook] User found: {user.username} (ID:{user_id})")
            return user
        logger.warning(f"[Webhook] User ID:{user_id} not found — using superadmin")

    # Fallback — superadmin
    superadmin = User.objects.filter(is_superuser=True).first()
    logger.info(f"[Webhook] Using superadmin: {superadmin}")
    return superadmin


# ─────────────────────────────────────────────────────────────────────────────
# WHATSAPP WEBHOOK
# ─────────────────────────────────────────────────────────────────────────────
@csrf_exempt
def whatsapp_webhook(request):
    if request.method == 'GET':
        return _verify_webhook(request)
    if request.method == 'POST':
        return _handle_incoming_message(request)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


def _verify_webhook(request):
    mode      = request.GET.get('hub.mode')
    token     = request.GET.get('hub.verify_token')
    challenge = request.GET.get('hub.challenge')
    logger.info(f"[Webhook] Verify | mode={mode} | token={token}")
    if mode == 'subscribe' and token == VERIFY_TOKEN:
        logger.info('[Webhook] ✅ Verified!')
        return HttpResponse(challenge, status=200, content_type='text/plain')
    logger.warning('[Webhook] ❌ Verification failed!')
    return HttpResponse('Forbidden', status=403)


def _handle_incoming_message(request):
    try:
        data     = json.loads(request.body)
        entry    = data.get('entry', [])
        if not entry:
            return JsonResponse({'status': 'no_entry'})
        changes  = entry[0].get('changes', [])
        if not changes:
            return JsonResponse({'status': 'no_changes'})
        value    = changes[0].get('value', {})
        messages = value.get('messages', [])
        if not messages:
            return JsonResponse({'status': 'no_message'})
        msg      = messages[0]
        if msg.get('type') != 'text':
            return JsonResponse({'status': 'non_text_ignored'})

        phone    = msg.get('from', '')
        text     = msg.get('text', {}).get('body', '').strip()
        contacts = value.get('contacts', [])
        name     = contacts[0].get('profile', {}).get('name', '') if contacts else ''
        if not name:
            name = f'WA-{phone[-4:]}' if phone else 'WhatsApp Lead'

        # WhatsApp webhook ke liye user_id URL se lo
        user_id = request.GET.get('user_id')
        lead    = _create_lead_from_whatsapp(name, phone, text, user_id)

        if lead:
            return JsonResponse({'status': 'lead_created', 'lead_id': lead.pk, 'name': lead.name})
        return JsonResponse({'status': 'existing_lead'})

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f'[Webhook] Error: {e}', exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


def _create_lead_from_whatsapp(name, phone, message, user_id=None):
    from .models import Lead
    phone_suffix = phone[-10:] if len(phone) >= 10 else phone
    existing = Lead.objects.filter(phone__icontains=phone_suffix).first()
    if existing:
        return None

    user = _get_user(user_id)
    lead = Lead.objects.create(
        name         = name,
        phone        = phone,
        source       = 'Other',
        status       = 'not-contacted',
        priority     = 'medium',
        notes        = f'WhatsApp Inquiry: {message}',
        company_name = 'Unknown',
        created_by   = user,
    )
    logger.info(f"[Webhook] ✅ WhatsApp Lead created — ID:{lead.pk} | User:{user}")
    return lead


# ─────────────────────────────────────────────────────────────────────────────
# GOOGLE FORM WEBHOOK — Multi-tenant
# ─────────────────────────────────────────────────────────────────────────────
@csrf_exempt
def google_form_webhook(request):
    """
    Google Form se leads receive karo.

    URL examples:
      Org 25: POST /api/crm/leads/webhook/google-form/?user_id=25
      Org 26: POST /api/crm/leads/webhook/google-form/?user_id=26
      Default: POST /api/crm/leads/webhook/google-form/
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    try:
        data    = json.loads(request.body)
        name    = data.get('name', '').strip()
        email   = data.get('email', '').strip()
        phone   = str(data.get('phone', '')).strip()
        message = data.get('message', '').strip()
        company = data.get('company', '').strip()

        if not name:
            return JsonResponse({'error': 'name required'}, status=400)

        # ── User lo — URL se user_id ──────────────────────────────────────
        user_id = request.GET.get('user_id')
        user    = _get_user(user_id)

        from .models import Lead

        # Duplicate check — same email + same user
        if email:
            existing = Lead.objects.filter(
                email__iexact = email,
                created_by    = user,
            ).first()
            if existing:
                logger.info(f"[GoogleForm] Lead exists for {email} — ID:{existing.pk}")
                return JsonResponse({'status': 'existing', 'lead_id': existing.pk})

        # Lead create karo
        lead = Lead.objects.create(
            name         = name,
            email        = email,
            phone        = phone,
            source       = 'Website',
            status       = 'not-contacted',
            priority     = 'medium',
            notes        = f'Google Form Inquiry: {message}',
            company_name = company or 'Unknown',
            created_by   = user,
        )
        logger.info(f"[GoogleForm] ✅ Lead created — ID:{lead.pk} | User:{user} | Name:{name}")
        return JsonResponse({
            'status':  'created',
            'lead_id': lead.pk,
            'name':    lead.name,
            'org_user': str(user),
        }, status=201)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f'[GoogleForm] Error: {e}', exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)
"""
settings_automation.py
───────────────────────
Yeh code apne main settings.py mein PASTE karo.
File ka naam change mat karo — yeh sirf reference hai.

INSTRUCTIONS:
1. Gmail App Password banana:
   → myaccount.google.com → Security → 2-Step Verification → App Passwords
   → App name: "NextGen CRM" → Generate → 16 digit password copy karo

2. Meta WhatsApp setup:
   → developers.facebook.com/apps → Create App → Business
   → Add WhatsApp product
   → Phone Number verify karo
   → Phone ID aur Access Token copy karo
   → Verify Token: nextgencrm_verify_2024 (ya jo chahe set karo)
"""

# ── EMAIL — Gmail SMTP (Free) ─────────────────────────────────────────────────
EMAIL_BACKEND       = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST          = 'smtp.gmail.com'
EMAIL_PORT          = 587
EMAIL_USE_TLS       = True
EMAIL_HOST_USER     = 'your_gmail@gmail.com'          # ← apna Gmail
EMAIL_HOST_PASSWORD = 'xxxx xxxx xxxx xxxx'           # ← 16 digit App Password
DEFAULT_FROM_EMAIL  = 'NextGen CRM <your_gmail@gmail.com>'

# ── WHATSAPP — Meta Cloud API (Free 1000/month) ───────────────────────────────
WHATSAPP_PHONE_ID     = 'your_phone_number_id'        # ← Meta Console se
WHATSAPP_ACCESS_TOKEN = 'EAAxxxxxxxxxxxxxxx'          # ← Meta Console se
WHATSAPP_VERIFY_TOKEN = 'nextgencrm_verify_2024'      # ← Webhook verify ke liye

# ── LOGGING — Development mein signals debug karna ho to ─────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {module}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class':     'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'crmapp.crm.leads': {
            'handlers': ['console'],
            'level':    'DEBUG',
            'propagate': False,
        },
    },
}
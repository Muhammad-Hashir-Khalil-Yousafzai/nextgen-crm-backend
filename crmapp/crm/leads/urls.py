from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views         import LeadViewSet, LeadNoteViewSet
from .webhook_views import whatsapp_webhook, google_form_webhook

router = DefaultRouter()
router.register(r'notes', LeadNoteViewSet, basename='lead-note')
router.register(r'',      LeadViewSet,     basename='lead')

urlpatterns = [
    # ── Webhooks ──────────────────────────────────────────────────
    path('webhook/whatsapp/',    whatsapp_webhook,    name='whatsapp-webhook'),
    path('webhook/google-form/', google_form_webhook, name='google-form-webhook'),

    # ── Standard CRUD routes ──────────────────────────────────────
    path('', include(router.urls)),
]
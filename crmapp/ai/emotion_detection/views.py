from datetime import timedelta
import secrets
import hashlib
import base64
import requests

from django.utils import timezone
from django.db.models import Count, Avg
from django.core.mail import send_mail
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import redirect

from google_auth_oauthlib.flow import Flow
from django.conf import settings

from .models import GmailConnection, EmotionDetection, AlertRule, AlertLog
from .serializers import (
    GmailConnectionSerializer,
    EmotionDetectionSerializer,
    AlertRuleSerializer,
    AlertLogSerializer,
    DashboardStatsSerializer,
)
from .services.gmail_service import fetch_unread_emails
from .services.emotion_service import classify_emotion


# ── Gmail OAuth ───────────────────────────────────────────────────────────────

class GmailOAuthInitView(APIView):
    """
    Step 1: Generate Google OAuth URL.
    Frontend redirects business to this URL to approve Gmail access.
    Supports adding MULTIPLE Gmail accounts — each call starts a fresh OAuth flow.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        code_verifier  = secrets.token_urlsafe(64)
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).rstrip(b'=').decode()

        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id":     settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
                    "token_uri":     "https://oauth2.googleapis.com/token",
                    "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
                }
            },
            scopes=["https://www.googleapis.com/auth/gmail.modify"],
        )
        flow.redirect_uri = settings.GOOGLE_REDIRECT_URI

        auth_url, state = flow.authorization_url(
            access_type            = "offline",
            include_granted_scopes = "true",
            prompt                 = "consent select_account",  # always show account picker
            code_challenge         = code_challenge,
            code_challenge_method  = "S256",
        )

        request.session["oauth_state"]         = state
        request.session["oauth_code_verifier"] = code_verifier
        request.session["oauth_user_id"]       = request.user.id  # remember who started this
        request.session.modified = True

        return Response({"auth_url": auth_url})


class GmailOAuthCallbackView(APIView):
    """
    Step 2: Google redirects here after business approves.
    Exchange code for tokens and save a NEW GmailConnection (doesn't overwrite existing ones).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        code  = request.query_params.get("code")
        state = request.query_params.get("state")

        if not code:
            return Response({"error": "No code returned from Google."}, status=400)

        stored_state  = request.session.get("oauth_state")
        code_verifier = request.session.get("oauth_code_verifier")

        if stored_state and state != stored_state:
            return Response({"error": "Invalid OAuth state."}, status=400)

        request.session.pop("oauth_state", None)
        request.session.pop("oauth_code_verifier", None)
        request.session.pop("oauth_user_id", None)

        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id":     settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
                    "token_uri":     "https://oauth2.googleapis.com/token",
                    "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
                }
            },
            scopes=["https://www.googleapis.com/auth/gmail.modify"],
            state=state,
        )
        flow.redirect_uri = settings.GOOGLE_REDIRECT_URI
        flow.fetch_token(code=code, code_verifier=code_verifier)

        creds = flow.credentials

        from googleapiclient.discovery import build
        service       = build("gmail", "v1", credentials=creds)
        profile       = service.users().getProfile(userId="me").execute()
        gmail_address = profile["emailAddress"]

        # Create OR reactivate — but DON'T overwrite other connections for this user
        connection, created = GmailConnection.objects.update_or_create(
            user          = request.user,
            gmail_address = gmail_address,
            defaults = {
                "access_token":  creds.token,
                "refresh_token": creds.refresh_token,
                "token_expiry":  creds.expiry,
                "is_active":     True,
            }
        )

# Redirect back to React app instead of showing raw JSON
        frontend_url = (
            f"http://localhost:3000/ai/emotion/emotion"
            f"?connected=true&email={gmail_address}"
        )
        return redirect(frontend_url)

# ── Multiple Gmail Connections ────────────────────────────────────────────────

class GmailConnectionListView(APIView):
    """
    Returns ALL Gmail accounts connected by this business.
    Used to render the list in the Gmail Connect tab.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        connections = GmailConnection.objects.filter(user=request.user).order_by("-connected_at")
        return Response(GmailConnectionSerializer(connections, many=True).data)


class GmailDisconnectView(APIView):
    """Disconnect ONE specific Gmail connection by ID."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            conn = GmailConnection.objects.get(pk=pk, user=request.user)
        except GmailConnection.DoesNotExist:
            return Response({"error": "Gmail connection not found."}, status=404)

        conn.is_active = False
        conn.save(update_fields=["is_active"])
        return Response({"message": f"{conn.gmail_address} disconnected."})


# ── Individual Sync ───────────────────────────────────────────────────────────

class GmailSyncView(APIView):
    """
    Manually trigger fetch + classify cycle for ONE specific Gmail connection.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            connection = GmailConnection.objects.get(
                pk=pk, user=request.user, is_active=True
            )
        except GmailConnection.DoesNotExist:
            return Response({"error": "Active Gmail connection not found."}, status=404)

        emails  = fetch_unread_emails(connection)
        created = []

        for em in emails:
            result = classify_emotion(em["full_text"])

            detection, is_new = EmotionDetection.objects.get_or_create(
                gmail_message_id = em["gmail_message_id"],
                defaults = {
                    "user":               request.user,
                    "gmail_connection":   connection,
                    "customer_name":      em["customer_name"],
                    "customer_email":     em["customer_email"],
                    "email_subject":      em["subject"],
                    "email_body_snippet": em["body_snippet"],
                    "emotion":            result["emotion"],
                    "intensity":          result["intensity"],
                    "confidence":         result["confidence"],
                }
            )

            if not is_new:
                continue

            _evaluate_alert_rules(request.user, detection)
            created.append(detection)

        connection.last_synced_at = timezone.now()
        connection.save(update_fields=["last_synced_at"])

        return Response({
            "gmail_address": connection.gmail_address,
            "synced":  len(emails),
            "new":     len(created),
            "message": f"{len(created)} new emails classified from {connection.gmail_address}.",
        })


# ── Detections ────────────────────────────────────────────────────────────────

class DetectionListView(APIView):
    """
    Returns latest emotion detections for logged-in business.
    Supports filters: ?emotion=angry&intensity=high&email=x&date=YYYY-MM-DD&gmail_id=3
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = EmotionDetection.objects.filter(user=request.user)

        emotion   = request.query_params.get("emotion")
        intensity = request.query_params.get("intensity")
        email     = request.query_params.get("email")
        date      = request.query_params.get("date")
        gmail_id  = request.query_params.get("gmail_id")   # NEW — filter by which inbox

        if emotion:
            qs = qs.filter(emotion=emotion)
        if intensity:
            qs = qs.filter(intensity=intensity)
        if email:
            qs = qs.filter(customer_email__icontains=email)
        if date:
            qs = qs.filter(detected_at__date=date)
        if gmail_id:
            qs = qs.filter(gmail_connection_id=gmail_id)

        qs = qs.order_by("-detected_at")[:50]
        return Response(EmotionDetectionSerializer(qs, many=True).data)


# ── Alert Rules ───────────────────────────────────────────────────────────────

class AlertRuleListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        rules = AlertRule.objects.filter(user=request.user)
        return Response(AlertRuleSerializer(rules, many=True).data)

    def post(self, request):
        serializer = AlertRuleSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class AlertRuleDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_rule(self, pk, user):
        try:
            return AlertRule.objects.get(pk=pk, user=user)
        except AlertRule.DoesNotExist:
            return None

    def patch(self, request, pk):
        rule = self._get_rule(pk, request.user)
        if not rule:
            return Response({"error": "Not found."}, status=404)
        serializer = AlertRuleSerializer(rule, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    def delete(self, request, pk):
        rule = self._get_rule(pk, request.user)
        if not rule:
            return Response({"error": "Not found."}, status=404)
        rule.delete()
        return Response(status=204)


# ── Alert Logs ────────────────────────────────────────────────────────────────

class AlertLogListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        logs = AlertLog.objects.filter(
            detection__user=request.user
        ).order_by("-fired_at")[:20]
        return Response(AlertLogSerializer(logs, many=True).data)


# ── Dashboard Stats ───────────────────────────────────────────────────────────

class DashboardStatsView(APIView):
    """
    Returns KPI numbers aggregated across ALL connected Gmail accounts.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.now().date()

        qs_today = EmotionDetection.objects.filter(
            user=request.user,
            detected_at__date=today,
        )

        total_today    = qs_today.count()
        alerts_today   = AlertLog.objects.filter(
            detection__user=request.user,
            fired_at__date=today,
        ).count()
        avg_confidence = qs_today.aggregate(a=Avg("confidence"))["a"] or 0
        customers      = EmotionDetection.objects.filter(
            user=request.user
        ).values("customer_email").distinct().count()

        top_emo = (
            qs_today.values("emotion")
            .annotate(c=Count("emotion"))
            .order_by("-c")
            .first()
        )
        dominant = top_emo["emotion"] if top_emo else "neutral"

        negative = qs_today.filter(
            emotion__in=["angry", "sad", "fearful"]
        ).count()
        negative_rate = round((negative / total_today * 100), 1) if total_today else 0

        # Across ALL connected Gmails now
        active_connections = GmailConnection.objects.filter(user=request.user, is_active=True)
        gmail_connected = active_connections.exists()
        last_synced     = active_connections.order_by("-last_synced_at").first()
        last_synced_at  = last_synced.last_synced_at if last_synced else None

        data = {
            "emails_today":      total_today,
            "alerts_triggered":  alerts_today,
            "avg_confidence":    round(avg_confidence * 100, 1),
            "customers_tracked": customers,
            "dominant_emotion":  dominant,
            "negative_rate":     negative_rate,
            "gmail_connected":   gmail_connected,
            "last_synced_at":    last_synced_at,
        }
        return Response(DashboardStatsSerializer(data).data)


# ── Internal helpers ──────────────────────────────────────────────────────────

INTENSITY_RANK = {"low": 1, "medium": 2, "high": 3}


def _evaluate_alert_rules(user, detection: EmotionDetection):
    rules = AlertRule.objects.filter(
        user       = user,
        emotion    = detection.emotion,
        is_enabled = True,
    )

    for rule in rules:
        if INTENSITY_RANK.get(detection.intensity, 0) >= INTENSITY_RANK.get(rule.threshold, 0):
            error_msg = None
            try:
                if rule.channel == "slack":
                    _send_slack(rule, detection)
                elif rule.channel == "email":
                    _send_email(rule, detection, user)
            except Exception as e:
                error_msg = str(e)

            AlertLog.objects.create(
                rule      = rule,
                detection = detection,
                action    = rule.action,
                channel   = rule.channel,
                status    = "failed" if error_msg else "actioned",
                error_msg = error_msg,
            )

            detection.alert_fired  = True
            detection.action_taken = rule.action
            detection.save(update_fields=["alert_fired", "action_taken"])
            break


def _send_slack(rule: AlertRule, detection: EmotionDetection):
    webhook_url = getattr(settings, "SLACK_WEBHOOK_URL", None)
    if not webhook_url:
        return

    emoji = {
        "angry":     "😡",
        "sad":       "😢",
        "fearful":   "😨",
        "surprised": "😮",
        "happy":     "😊",
        "neutral":   "😐",
    }.get(detection.emotion, "🔔")

    payload = {
        "text": (
            f"{emoji} *Emotion Alert — {rule.action}*\n"
            f"*Customer:* {detection.customer_email}\n"
            f"*Emotion:* {detection.emotion.capitalize()} "
            f"({detection.intensity} intensity, {detection.confidence_pct}% confidence)\n"
            f"*Subject:* {detection.email_subject}"
        )
    }
    response = requests.post(webhook_url, json=payload, timeout=5)
    response.raise_for_status()


def _send_email(rule: AlertRule, detection: EmotionDetection, user):
    send_mail(
        subject    = f"[Emotion Alert] {rule.action}",
        message    = (
            f"Alert triggered!\n\n"
            f"Customer:   {detection.customer_email}\n"
            f"Emotion:    {detection.emotion.capitalize()} "
            f"({detection.intensity} intensity, {detection.confidence_pct}% confidence)\n"
            f"Subject:    {detection.email_subject}\n"
            f"Action:     {rule.action}\n"
            f"Detected:   {detection.detected_at:%Y-%m-%d %H:%M UTC}"
        ),
        from_email     = None,
        recipient_list = [user.email],
        fail_silently  = False,
    )
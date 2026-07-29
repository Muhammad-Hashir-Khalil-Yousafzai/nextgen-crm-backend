"""
crmapp/ai/recommendation/views.py

All endpoints under /api/ai/recommendation/

GET  dashboard/stats/               → KPI numbers
GET  profiles/                      → user profiles list
POST profiles/build/                → build/refresh a single profile
GET  recommendations/               → recommendation log
POST recommendations/generate/      → generate recs for a profile
POST recommendations/{id}/feedback/ → record feedback event
GET  models/                        → model accuracy/coverage data
GET  channels/                      → channel performance breakdown
GET  abtests/                       → A/B test registry
POST abtests/{id}/compute/          → recompute lift + confidence
GET  feedback/                      → feedback events log
GET  performance/                   → monthly performance trend
GET  proactive/alerts/              → open proactive alerts
POST proactive/alerts/{id}/resolve/ → mark alert resolved
POST proactive/run/                 → manually trigger signal scan
"""

import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

from .models import (
    UserProfile,
    RecommendationItem,
    ABTest,
    ProactiveAlert,
)
from .serializers import (
    UserProfileSerializer,
    RecommendationItemSerializer,
    RecommendationListSerializer,
    FeedbackEventSerializer,
    ABTestSerializer,
    ChannelPerformanceSerializer,
    ModelPerformanceSerializer,
    ProactiveAlertSerializer,
    DashboardStatsSerializer,
)
from . import services

logger = logging.getLogger(__name__)


# ── Dashboard ─────────────────────────────────────────────────────────────────

class DashboardStatsView(APIView):
    """GET /dashboard/stats/ → KPI numbers for the overview strip."""
    permission_classes = [AllowAny]

    def get(self, request):
        data = services.get_dashboard_stats()
        return Response(DashboardStatsSerializer(data).data)


# ── User Profiles ─────────────────────────────────────────────────────────────

class ProfileListView(APIView):
    """GET /profiles/ → paginated list of UserProfiles ordered by engagement score."""
    permission_classes = [AllowAny]

    def get(self, request):
        limit   = int(request.query_params.get("limit", 50))
        segment = request.query_params.get("segment")

        qs = UserProfile.objects.order_by("-engagement_score")
        if segment:
            qs = qs.filter(segment=segment)
        qs = qs[:limit]

        serializer = UserProfileSerializer(qs, many=True)
        return Response(serializer.data)


class ProfileBuildView(APIView):
    """
    POST /profiles/build/
    Body: { "subject_type": "lead", "subject_id": "42" }
    Builds or refreshes a UserProfile from live CRM data.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        subject_type = request.data.get("subject_type", "lead")
        subject_id   = request.data.get("subject_id")

        if not subject_id:
            return Response(
                {"error": "subject_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            profile = services.build_user_profile(subject_type, str(subject_id))
            return Response({
                "success": True,
                "profile": UserProfileSerializer(profile).data,
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"[REC] ProfileBuildView error: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProfileDetailView(APIView):
    """GET /profiles/{profile_id}/ → single profile detail."""
    permission_classes = [AllowAny]

    def get(self, request, pk):
        try:
            profile = UserProfile.objects.get(pk=pk)
            return Response(UserProfileSerializer(profile).data)
        except UserProfile.DoesNotExist:
            return Response({"error": "Profile not found."}, status=status.HTTP_404_NOT_FOUND)


# ── Recommendations ───────────────────────────────────────────────────────────

class RecommendationListView(APIView):
    """
    GET /recommendations/
    Supports: ?status=pending|delivered|clicked|converted&limit=50&is_proactive=true
    """
    permission_classes = [AllowAny]

    def get(self, request):
        limit        = int(request.query_params.get("limit", 50))
        filter_status = request.query_params.get("status")
        is_proactive  = request.query_params.get("is_proactive")

        qs = RecommendationItem.objects.select_related("profile").order_by("-relevance_score", "-created_at")

        if filter_status:
            qs = qs.filter(status=filter_status)
        if is_proactive is not None:
            qs = qs.filter(is_proactive=(is_proactive.lower() == "true"))

        qs = qs[:limit]
        serializer = RecommendationListSerializer(qs, many=True)
        return Response(serializer.data)


class RecommendationGenerateView(APIView):
    """
    POST /recommendations/generate/
    Body: { "profile_id": "prof-abc" }  OR  { "subject_type": "lead", "subject_id": "42" }
    Generates top-N recommendations for the given profile.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        profile_id   = request.data.get("profile_id")
        subject_type = request.data.get("subject_type", "lead")
        subject_id   = request.data.get("subject_id")

        try:
            if profile_id:
                profile = UserProfile.objects.get(pk=profile_id)
            elif subject_id:
                profile = services.build_user_profile(subject_type, str(subject_id))
            else:
                return Response(
                    {"error": "Provide profile_id or subject_id."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            recs = services.generate_recommendations(profile)
            return Response({
                "success":  True,
                "count":    len(recs),
                "recs":     RecommendationItemSerializer(recs, many=True).data,
            }, status=status.HTTP_201_CREATED)

        except UserProfile.DoesNotExist:
            return Response({"error": "Profile not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"[REC] RecommendationGenerateView error: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RecommendationDetailView(APIView):
    """GET /recommendations/{id}/ → full recommendation detail with reasons."""
    permission_classes = [AllowAny]

    def get(self, request, pk):
        try:
            rec = RecommendationItem.objects.select_related("profile", "proactive_alert").get(pk=pk)
            return Response(RecommendationItemSerializer(rec).data)
        except RecommendationItem.DoesNotExist:
            return Response({"error": "Recommendation not found."}, status=status.HTTP_404_NOT_FOUND)


class RecommendationFeedbackView(APIView):
    """
    POST /recommendations/{id}/feedback/
    Body: { "action": "clicked", "revenue": 0.0 }
    Records a feedback event and updates recommendation status.
    """
    permission_classes = [AllowAny]

    def post(self, request, pk):
        action  = request.data.get("action")
        revenue = float(request.data.get("revenue", 0.0))

        if not action:
            return Response({"error": "action is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            feedback = services.record_feedback(pk, action, revenue)
            return Response({
                "success":  True,
                "feedback": FeedbackEventSerializer(feedback).data,
            })
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"[REC] feedback error: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ── Models ────────────────────────────────────────────────────────────────────

class ModelsDataView(APIView):
    """GET /models/ → accuracy, coverage, latency per model type."""
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(services.get_models_data())


# ── Channels ──────────────────────────────────────────────────────────────────

class ChannelsDataView(APIView):
    """GET /channels/ → aggregated channel performance."""
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(services.get_channels_data())


# ── A/B Tests ─────────────────────────────────────────────────────────────────

class ABTestListView(APIView):
    """GET /abtests/ → all A/B tests."""
    permission_classes = [AllowAny]

    def get(self, request):
        tests = ABTest.objects.all().order_by("-created_at")
        return Response(ABTestSerializer(tests, many=True).data)


class ABTestCreateView(APIView):
    """
    POST /abtests/create/
    Body: { "name": "...", "control_label": "...", "treatment_label": "...", "primary_metric": "ctr" }
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ABTestSerializer(data=request.data)
        if serializer.is_valid():
            test = serializer.save()
            return Response(ABTestSerializer(test).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ABTestComputeView(APIView):
    """
    POST /abtests/{id}/compute/
    Recomputes lift and statistical confidence for a running test.
    """
    permission_classes = [AllowAny]

    def post(self, request, pk):
        try:
            test = ABTest.objects.get(pk=pk)
        except ABTest.DoesNotExist:
            return Response({"error": "A/B test not found."}, status=status.HTTP_404_NOT_FOUND)

        results = services.compute_ab_results(test)
        return Response({
            "success": True,
            "results": results,
            "test":    ABTestSerializer(test).data,
        })


# ── Feedback ──────────────────────────────────────────────────────────────────

class FeedbackListView(APIView):
    """GET /feedback/ → recent feedback events."""
    permission_classes = [AllowAny]

    def get(self, request):
        limit = int(request.query_params.get("limit", 30))
        return Response(services.get_feedback_data(limit=limit))


# ── Performance ───────────────────────────────────────────────────────────────

class PerformanceDataView(APIView):
    """GET /performance/ → monthly CTR / conv / revenue / precision trend."""
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(services.get_performance_data())


# ── Proactive Alerts ──────────────────────────────────────────────────────────

class ProactiveAlertListView(APIView):
    """
    GET /proactive/alerts/
    Query params: ?resolved=false (default) | ?resolved=true
    """
    permission_classes = [AllowAny]

    def get(self, request):
        resolved = request.query_params.get("resolved", "false").lower() == "true"
        limit    = int(request.query_params.get("limit", 20))
        return Response(services.get_proactive_alerts_data(resolved=resolved, limit=limit))


class ProactiveAlertResolveView(APIView):
    """POST /proactive/alerts/{id}/resolve/ → mark alert as resolved."""
    permission_classes = [AllowAny]

    def post(self, request, pk):
        try:
            alert = ProactiveAlert.objects.get(pk=pk)
        except ProactiveAlert.DoesNotExist:
            return Response({"error": "Alert not found."}, status=status.HTTP_404_NOT_FOUND)

        from django.utils import timezone
        alert.resolved    = True
        alert.resolved_at = timezone.now()
        alert.save(update_fields=["resolved", "resolved_at"])

        return Response({
            "success": True,
            "message": f"Alert '{alert.trigger_type}' for {alert.profile.subject_name} resolved.",
        })


class ProactiveRunView(APIView):
    """
    POST /proactive/run/
    Manually triggers the proactive signal scan (normally run by Celery).
    Useful for testing and manual refresh from the frontend.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            fired_count = services.check_proactive_signals()
            return Response({
                "success":     True,
                "alerts_fired": fired_count,
                "message":     f"Signal scan complete. {fired_count} new alert(s) fired.",
            })
        except Exception as e:
            logger.error(f"[REC] ProactiveRunView error: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
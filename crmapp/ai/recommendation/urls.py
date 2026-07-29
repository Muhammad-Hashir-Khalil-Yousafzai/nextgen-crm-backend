"""
crmapp/ai/recommendation/urls.py

All routes mount under /api/ai/recommendation/
"""

from django.urls import path
from .views import (
    DashboardStatsView,
    ProfileListView,
    ProfileBuildView,
    ProfileDetailView,
    RecommendationListView,
    RecommendationGenerateView,
    RecommendationDetailView,
    RecommendationFeedbackView,
    ModelsDataView,
    ChannelsDataView,
    ABTestListView,
    ABTestCreateView,
    ABTestComputeView,
    FeedbackListView,
    PerformanceDataView,
    ProactiveAlertListView,
    ProactiveAlertResolveView,
    ProactiveRunView,
)

urlpatterns = [

    # ── Dashboard ────────────────────────────────────────────────────────────
    path("dashboard/stats/",            DashboardStatsView.as_view(),         name="rec-dashboard-stats"),

    # ── User Profiles ─────────────────────────────────────────────────────────
    path("profiles/",                   ProfileListView.as_view(),             name="rec-profiles"),
    path("profiles/build/",             ProfileBuildView.as_view(),            name="rec-profiles-build"),
    path("profiles/<str:pk>/",          ProfileDetailView.as_view(),           name="rec-profile-detail"),

    # ── Recommendations ───────────────────────────────────────────────────────
    path("recommendations/",            RecommendationListView.as_view(),      name="rec-list"),
    path("recommendations/generate/",   RecommendationGenerateView.as_view(),  name="rec-generate"),
    path("recommendations/<str:pk>/",           RecommendationDetailView.as_view(),    name="rec-detail"),
    path("recommendations/<str:pk>/feedback/",  RecommendationFeedbackView.as_view(),  name="rec-feedback"),

    # ── Models ────────────────────────────────────────────────────────────────
    path("models/",                     ModelsDataView.as_view(),              name="rec-models"),

    # ── Channels ──────────────────────────────────────────────────────────────
    path("channels/",                   ChannelsDataView.as_view(),            name="rec-channels"),

    # ── A/B Tests ─────────────────────────────────────────────────────────────
    path("abtests/",                    ABTestListView.as_view(),              name="rec-abtests"),
    path("abtests/create/",             ABTestCreateView.as_view(),            name="rec-abtest-create"),
    path("abtests/<str:pk>/compute/",   ABTestComputeView.as_view(),           name="rec-abtest-compute"),

    # ── Feedback Events ───────────────────────────────────────────────────────
    path("feedback/",                   FeedbackListView.as_view(),            name="rec-feedback-list"),

    # ── Performance ───────────────────────────────────────────────────────────
    path("performance/",                PerformanceDataView.as_view(),         name="rec-performance"),

    # ── Proactive ─────────────────────────────────────────────────────────────
    path("proactive/alerts/",                           ProactiveAlertListView.as_view(),    name="rec-proactive-alerts"),
    path("proactive/alerts/<str:pk>/resolve/",          ProactiveAlertResolveView.as_view(), name="rec-proactive-resolve"),
    path("proactive/run/",                              ProactiveRunView.as_view(),          name="rec-proactive-run"),
]
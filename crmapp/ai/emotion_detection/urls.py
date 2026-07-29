from django.urls import path
from .views import (
    GmailOAuthInitView,
    GmailOAuthCallbackView,
    GmailConnectionListView,
    GmailDisconnectView,
    GmailSyncView,
    DetectionListView,
    AlertRuleListCreateView,
    AlertRuleDetailView,
    AlertLogListView,
    DashboardStatsView,
)

urlpatterns = [
    # Gmail OAuth
    path("gmail/connect/",                GmailOAuthInitView.as_view(),     name="gmail-connect"),
    path("gmail/callback/",                GmailOAuthCallbackView.as_view(), name="gmail-callback"),

    # Multiple Gmail connections
    path("gmail/connections/",             GmailConnectionListView.as_view(), name="gmail-connections"),
    path("gmail/connections/<int:pk>/disconnect/", GmailDisconnectView.as_view(), name="gmail-disconnect"),
    path("gmail/connections/<int:pk>/sync/",       GmailSyncView.as_view(),       name="gmail-sync"),

    # Detections
    path("detections/",       DetectionListView.as_view(),      name="detections"),

    # Alert rules
    path("alert-rules/",      AlertRuleListCreateView.as_view(),name="alert-rules"),
    path("alert-rules/<int:pk>/", AlertRuleDetailView.as_view(),name="alert-rule-detail"),

    # Alert logs
    path("alert-logs/",       AlertLogListView.as_view(),       name="alert-logs"),

    # Dashboard KPIs
    path("stats/",            DashboardStatsView.as_view(),     name="dashboard-stats"),
]
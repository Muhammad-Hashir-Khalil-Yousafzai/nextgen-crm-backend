"""
Analytics URL Configuration
============================
Include in backend/urls.py:

    path("api/analytics/", include("crmapp.analytics.urls")),
"""

from django.urls import path
from . import views

urlpatterns = [
    # ── Standard analytics ────────────────────────────────────────────────────
    path("sales/",     views.sales_analytics,    name="analytics-sales"),
    path("customers/", views.customer_analytics,  name="analytics-customers"),
    path("support/",   views.support_analytics,   name="analytics-support"),
    path("surveys/",   views.survey_analytics,    name="analytics-surveys"),

    # ── AI model endpoints ────────────────────────────────────────────────────
    path("ai/leads/",   views.ai_lead_scores,   name="analytics-ai-leads"),
    path("ai/churn/",   views.ai_churn_predict,  name="analytics-ai-churn"),
    path("ai/forecast/",views.ai_forecast,       name="analytics-ai-forecast"),
    path("kpis/", views.kpi_analytics, name="analytics-kpis"),
    path("bi/", views.bi_analytics, name="analytics-bi"),
 
]
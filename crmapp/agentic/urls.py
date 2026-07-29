from django.urls import path, include

urlpatterns = [
    path('tasks/', include('crmapp.agentic.tasks.urls')),
    path('agents/', include('crmapp.agentic.agents.urls')),
    path("analytics/", include("crmapp.agentic.analytics.urls")),
]
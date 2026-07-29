from django.urls import path
from .views import DashboardSummaryView

urlpatterns = [
    path('<str:dashboard_name>/summary/', DashboardSummaryView.as_view()),
]
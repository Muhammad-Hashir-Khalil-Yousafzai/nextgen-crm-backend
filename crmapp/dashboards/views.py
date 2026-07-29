from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .permissions import HasDashboardPermission
from . import services

DASHBOARD_REGISTRY = {
    "hr": services.get_hr_dashboard,
    "employee": services.get_employee_dashboard,
    "finance": services.get_finance_dashboard,
    "sales": services.get_sales_dashboard,  # ✅ Sales Dashboard Added
    "sales": services.get_sales_dashboard,
    "operations": services.get_operations_dashboard,
    "marketing": services.get_marketing_dashboard,
    "crm": services.get_crm_dashboard,
    "superadmin": services.get_superadmin_dashboard,
    "admin": services.get_admin_dashboard, # ✅ Ye line add karein
    "main": services.get_superadmin_dashboard, # 'main' bhi superadmin ki tarah behave karega
    "support": services.get_support_dashboard,
    "analytics": services.get_analytics_dashboard, #
    "ai": services.get_ai_dashboard,
}


class DashboardSummaryView(APIView):
    permission_classes = [IsAuthenticated, HasDashboardPermission]

    def get(self, request, dashboard_name):
        func = DASHBOARD_REGISTRY.get(dashboard_name)
        if not func:
            return Response({"error": "Unknown dashboard"}, status=404)

        data = func(request)
        return Response(data)
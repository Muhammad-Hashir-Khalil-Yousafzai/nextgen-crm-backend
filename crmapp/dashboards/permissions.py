from rest_framework.permissions import BasePermission
from crmapp.system.roles.permissions import get_user_permissions


class HasDashboardPermission(BasePermission):
    """
    Checks dashboard access using the REAL permission system.
    """

    action = "view"

    DASHBOARD_MODULE_MAP = {
        "hr": "hr",
        "employee": "employee", 
        "crm": "crm",
        "sales": "sales",
        "marketing": "marketing",
        "finance": "finance",
        "operations": "operations",
        "project": "project",
        "support": "support",
        "analytics": "analytics",
        "insights": "analytics",
        "admin": "system",
        "superadmin": "system",
        "main": "system",
    }

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # ✅ Super Admin aur Staff ko sab kuch allow hai
        if request.user.is_superuser or request.user.is_staff:
            return True

        dashboard_name = view.kwargs.get("dashboard_name")
        module = self.DASHBOARD_MODULE_MAP.get(dashboard_name, dashboard_name)

        # ✅ FIX: In dashboards ko har login user dekh sakta hai
        if dashboard_name in ["main", "superadmin", "admin", "employee", "analytics", "support"]:
            return True

        # Baqi sab dashboards (jaise HR, Finance) ke liye proper module permission check karein
        perms = get_user_permissions(request.user)
        return perms.get(module, {}).get(self.action, False)
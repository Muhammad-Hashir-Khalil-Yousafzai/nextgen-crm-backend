from django.urls import path
from .views import (
    PayrollEmployeesView,
    PayrollRunListCreateView, PayrollRunDetailView,
    AddPayrollLineView, PayrollRunApproveView, PayrollRunMarkPaidView,
)

urlpatterns = [
    # ✅ FIXED: ab yeh HRM ka real Employee data return karta hai (UUID based)
    path('employees/', PayrollEmployeesView.as_view(), name='payroll-emp-list'),

    # ❌ REMOVED: employees/<int:pk>/ — HRM ke /api/employees/{uuid}/ use karo

    path('runs/',                    PayrollRunListCreateView.as_view(), name='payroll-run-list'),
    path('runs/<int:pk>/',           PayrollRunDetailView.as_view(),     name='payroll-run-detail'),
    path('runs/<int:pk>/add-line/',  AddPayrollLineView.as_view(),       name='payroll-add-line'),
    path('runs/<int:pk>/approve/',   PayrollRunApproveView.as_view(),    name='payroll-approve'),
    path('runs/<int:pk>/mark-paid/', PayrollRunMarkPaidView.as_view(),   name='payroll-paid'),
]
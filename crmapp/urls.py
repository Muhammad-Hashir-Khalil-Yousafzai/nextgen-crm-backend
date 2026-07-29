from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework_simplejwt.views import TokenRefreshView

from .views import CustomTokenObtainPairView

from .views import (
    # Original
    DepartmentViewSet,
    DesignationViewSet,
    EmployeeViewSet,
    AttendanceViewSet,
    LeaveViewSet,
    PayrollViewSet,
    PerformanceReviewViewSet,
    JobPostViewSet,
    CandidateViewSet,
    PromotionViewSet,
    ResignationViewSet,
    TerminationViewSet,
    employees_list,
    create_department,
    my_employee_profile,
    # New
    BankDetailsViewSet,
    EmergencyContactViewSet,
    FamilyMemberViewSet,
    EducationViewSet,
    ExperienceViewSet,
    ProjectViewSet,
    TaskViewSet,
    AssetViewSet,
)

router = DefaultRouter()

# ── Original routes ────────────────────────────────────────────────────────────
router.register(r'departments',         DepartmentViewSet,        basename='department')
router.register(r'designations',        DesignationViewSet,       basename='designation')
router.register(r'employees',           EmployeeViewSet,          basename='employee')
router.register(r'attendances',         AttendanceViewSet,        basename='attendance-legacy')  # ← kept from crm-url1 (legacy plural form)
router.register(r'attendance',          AttendanceViewSet,        basename='attendance')
router.register(r'leaves',              LeaveViewSet,             basename='leave')
router.register(r'payrolls',            PayrollViewSet,           basename='payroll')
router.register(r'performance-reviews', PerformanceReviewViewSet, basename='performance-review')
router.register(r'jobs',                JobPostViewSet,           basename='job')
router.register(r'candidates',          CandidateViewSet,         basename='candidate')
router.register(r'promotions',          PromotionViewSet,         basename='promotion')
router.register(r'resignations',        ResignationViewSet,       basename='resignation')
router.register(r'terminations',        TerminationViewSet,       basename='termination')

# ── New standalone routes ──────────────────────────────────────────────────────
router.register(r'bank-details',        BankDetailsViewSet,       basename='bank-detail')
router.register(r'emergency-contacts',  EmergencyContactViewSet,  basename='emergency-contact')
router.register(r'family-members',      FamilyMemberViewSet,      basename='family-member')
router.register(r'educations',          EducationViewSet,         basename='education')
router.register(r'experiences',         ExperienceViewSet,        basename='experience')
router.register(r'projects',            ProjectViewSet,           basename='project')
router.register(r'tasks',               TaskViewSet,              basename='task')
router.register(r'assets',              AssetViewSet,             basename='asset')

urlpatterns = [
    # ── MUST BE DECLARED FIRST ──────────────────────────────────────────────────
    # Catch /employees/me/ before the router thinks "me" is an ID
    path('employees/me/', my_employee_profile, name='employee-me'),

    # ── ROUTER URLS ─────────────────────────────────────────────────────────────
    path('', include(router.urls)),

    # ── LEGACY & AUTH ───────────────────────────────────────────────────────────
    path('employees-list/', employees_list, name='employees-list'),
    path('create-department/', create_department, name='create-department'),

    # JWT auth (current)
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Token auth (legacy, kept from crm-url1)
    path('token/', obtain_auth_token, name='api_token_auth'),

    # ── NESTED MODULE INCLUDES (kept from crm-url1) ─────────────────────────────
  
    # ── NESTED MODULE INCLUDES (kept from crm-url1) ─────────────────────────────
    path('agentic/', include('crmapp.agentic.urls')),  # ✅ only one agentic include
    path('crm/', include('crmapp.crm.urls')),
    path('ai/', include('crmapp.ai.urls')),
    path('automation/', include('crmapp.automation.urls')),
]
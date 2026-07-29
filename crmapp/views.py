from datetime import date, datetime, timedelta
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, action, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status, viewsets
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import CustomTokenObtainPairSerializer
from .system.roles.permissions import can
from .models import (
    Department,
    Designation,
    Employee,
    BankDetails,
    EmergencyContact,
    FamilyMember,
    Education,
    Experience,
    Project,
    Task,
    Asset,
    Attendance,
    Leave,
    Payroll,
    PerformanceReview,
    JobPost,
    Candidate,
    Promotion,
    Resignation,
    Termination,
    TerminationReinstatement,
)
from .serializers import (
    CustomTokenObtainPairSerializer,
    DepartmentSerializer,
    DesignationSerializer,
    EmployeeSerializer,
    EmployeeDetailSerializer,
    BankDetailsSerializer,
    EmergencyContactSerializer,
    FamilyMemberSerializer,
    EducationSerializer,
    ExperienceSerializer,
    ProjectSerializer,
    TaskSerializer,
    AssetSerializer,
    AttendanceSerializer,
    LeaveSerializer,
    PayrollSerializer,
    PerformanceReviewSerializer,
    JobPostSerializer,
    CandidateSerializer,
    PromotionSerializer,
    ResignationSerializer,
    TerminationSerializer,
    TerminationReinstatementSerializer,
)

# ======================================================
# PERMISSION HELPER
# ======================================================
def hr_permissions(self):
    action_map = {
        'list':           can('hr', 'view'),
        'retrieve':       can('hr', 'view'),
        'create':         can('hr', 'create'),
        'update':         can('hr', 'edit'),
        'partial_update': can('hr', 'edit'),
        'destroy':        can('hr', 'delete'),
    }
    return [action_map.get(self.action, can('hr', 'view'))()]

# ======================================================
# TENANT HELPER — employee bhi apna data dekh sake
# ======================================================
def get_owner_ids(user):
    """
    Returns list of user IDs jinke created_by se data filter hoga.
    SuperAdmin    → [khud ka id] + [sab HR/sub-users jo isne banaye]
    Employee user → [emp.created_by.id]
    Sub-user (HR) → [sub_user_ids created by same superadmin]
    """
    from crmapp.system.usermanage.models import UserProfile

    if user.is_superuser:
        owner_ids = [user.id]
        sub_ids = list(
            UserProfile.objects.filter(created_by=user).values_list('user_id', flat=True)
        )
        owner_ids.extend(sub_ids)
        return owner_ids

    # Employee user hai?
    try:
        emp = Employee.objects.get(user=user)
        if emp.created_by:
            return [emp.created_by_id]
    except Employee.DoesNotExist:
        pass

    # Normal sub-user (HR etc)
    try:
        profile = UserProfile.objects.get(user=user)
        if profile.created_by:
            sub_ids = list(
                UserProfile.objects.filter(
                    created_by=profile.created_by
                ).values_list('user_id', flat=True)
            )
            sub_ids.append(profile.created_by_id)
            return sub_ids
    except UserProfile.DoesNotExist:
        pass

    return [user.id]

# ======================================================
# FUNCTION BASED APIs (kept for backwards compatibility)
# ======================================================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def employees_list(request):
    owner_ids = get_owner_ids(request.user)
    qs = Employee.objects.filter(created_by__in=owner_ids)
    serializer = EmployeeSerializer(qs, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(['POST'])
def create_department(request):
    """POST /create-department/"""
    serializer = DepartmentSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(created_by=request.user)
        return Response(
            {"message": "Department created successfully", "data": serializer.data},
            status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_employee_profile(request):
    user = request.user
    employee = None
    try:
        employee = Employee.objects.get(email__iexact=user.email)
    except Employee.DoesNotExist:
        pass

    if employee is None:
        try:
            employee = Employee.objects.get(user=user)
        except (Employee.DoesNotExist, Exception):
            pass

    if employee is None:
        # Superuser / staff → admin
        if user.is_superuser or user.is_staff:
            return Response({
                "employee_uuid":       None,
                "employee_display_id": "ADMIN",
                "name":                user.username,
                "avatar":              None,
                "is_admin":            True,
            })

        # ✅ HR ya koi bhi sub-user jo khud employee nahi hai
        from crmapp.system.usermanage.models import UserProfile
        try:
            profile = UserProfile.objects.get(user=user)
            if profile.created_by:
                return Response({
                    "employee_uuid":       None,
                    "employee_display_id": "HR",
                    "name":                user.username,
                    "avatar":              None,
                    "is_admin":            True,
                })
        except UserProfile.DoesNotExist:
            pass

        return Response(
            {"detail": "No employee profile linked to this account."},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response({
        "employee_uuid":        str(employee.id),
        "employee_display_id":  employee.employee_id,
        "name":                 employee.name or employee.first_name or user.username,
        "avatar": (
            request.build_absolute_uri(employee.avatar.url)
            if employee.avatar else None
        ),
        "is_admin": user.is_superuser or user.is_staff,
    })
# ======================================================
# DEPARTMENT
# ======================================================
class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all().order_by('-created_at')
    serializer_class = DepartmentSerializer

    def get_permissions(self):
        return hr_permissions(self)

    def get_queryset(self):
        owner_ids    = get_owner_ids(self.request.user)
        qs           = super().get_queryset().filter(created_by__in=owner_ids)
        name         = self.request.query_params.get('name')
        status_param = self.request.query_params.get('status')
        if name:
            qs = qs.filter(name__icontains=name)
        if status_param:
            qs = qs.filter(status=status_param)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

# ======================================================
# DESIGNATION
# ======================================================
class DesignationViewSet(viewsets.ModelViewSet):
    queryset = Designation.objects.all().order_by('-created_at')
    serializer_class = DesignationSerializer

    def get_permissions(self):
        return hr_permissions(self)

    def get_queryset(self):
        owner_ids    = get_owner_ids(self.request.user)
        qs           = super().get_queryset().filter(created_by__in=owner_ids)
        department   = self.request.query_params.get('department')
        status_param = self.request.query_params.get('status')
        if department:
            qs = qs.filter(department_id=department)
        if status_param:
            qs = qs.filter(status=status_param)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

# ======================================================
# EMPLOYEE
# ======================================================
class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.select_related(
        'department', 'designation', 'bank_details'
    ).prefetch_related(
        'emergency_contacts', 'family_members', 'educations',
        'experiences', 'assets', 'performance_reviews', 'projects',
    ).order_by('-created_at')

    def get_permissions(self):
        return hr_permissions(self)

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return EmployeeDetailSerializer
        return EmployeeSerializer

    def get_queryset(self):
        owner_ids    = get_owner_ids(self.request.user)
        qs           = super().get_queryset().filter(created_by__in=owner_ids)
        department   = self.request.query_params.get('department')
        designation  = self.request.query_params.get('designation')
        status_param = self.request.query_params.get('status')
        team         = self.request.query_params.get('team')
        if department:
            qs = qs.filter(department_id=department)
        if designation:
            qs = qs.filter(designation_id=designation)
        if status_param:
            qs = qs.filter(status=status_param)
        if team:
            qs = qs.filter(team__icontains=team)
        return qs

    def perform_create(self, serializer):
        from django.contrib.auth.models import User
        from crmapp.system.roles.models import Role, UserRole
        from crmapp.system.usermanage.models import UserProfile

        hr_user  = self.request.user
        password = self.request.data.get('password', 'Employee@123')

        serializer.validated_data.pop('password', None)
        employee = serializer.save(created_by=hr_user)

        auth_user = User.objects.create_user(
            username=employee.email,
            email=employee.email,
            password=password,
            is_active=True
        )

        employee.user = auth_user
        employee.save(update_fields=['user'])

        # ✅ YE 3 LINES ADD KAREIN (Taake UserProfile bhi HR se link ho jaye)
        profile, _ = UserProfile.objects.get_or_create(user=auth_user)
        profile.created_by = hr_user
        profile.save(update_fields=['created_by'])

        employee_role = Role.objects.filter(name__iexact="Employee").first()
        if employee_role:
            UserRole.objects.get_or_create(
                user=auth_user,
                role=employee_role,
                defaults={'assigned_by': hr_user}
            )

    @action(detail=True, methods=['get', 'patch'], url_path='bank', url_name='bank')
    def bank(self, request, pk=None):
        employee = self.get_object()
        instance, _ = BankDetails.objects.get_or_create(employee=employee)
        if request.method == 'GET':
            return Response(BankDetailsSerializer(instance).data)
        serializer = BankDetailsSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=True, methods=['get', 'post'], url_path='emergency', url_name='emergency')
    def emergency(self, request, pk=None):
        employee = self.get_object()
        if request.method == 'GET':
            contacts = EmergencyContact.objects.filter(employee=employee)
            return Response(EmergencyContactSerializer(contacts, many=True).data)
        serializer = EmergencyContactSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(employee=employee)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get', 'post'], url_path='family', url_name='family')
    def family(self, request, pk=None):
        employee = self.get_object()
        if request.method == 'GET':
            members = FamilyMember.objects.filter(employee=employee)
            return Response(FamilyMemberSerializer(members, many=True).data)
        serializer = FamilyMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(employee=employee)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get', 'post'], url_path='education', url_name='education')
    def education(self, request, pk=None):
        employee = self.get_object()
        if request.method == 'GET':
            records = Education.objects.filter(employee=employee)
            return Response(EducationSerializer(records, many=True).data)
        serializer = EducationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(employee=employee)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get', 'post'], url_path='experience', url_name='experience')
    def experience(self, request, pk=None):
        employee = self.get_object()
        if request.method == 'GET':
            records = Experience.objects.filter(employee=employee)
            return Response(ExperienceSerializer(records, many=True).data)
        serializer = ExperienceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(employee=employee)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='assets', url_name='employee-assets')
    def assets(self, request, pk=None):
        employee = self.get_object()
        assets = Asset.objects.filter(assigned_to=employee).select_related('assigned_by')
        return Response(AssetSerializer(assets, many=True).data)

    @action(detail=True, methods=['get'], url_path='projects', url_name='employee-projects')
    def projects(self, request, pk=None):
        employee = self.get_object()
        projects = Project.objects.filter(
            members=employee
        ).prefetch_related('tasks').select_related('lead') | Project.objects.filter(
            lead=employee
        ).prefetch_related('tasks').select_related('lead')
        projects = projects.distinct()
        return Response(ProjectSerializer(projects, many=True).data)

    @action(detail=True, methods=['get'], url_path='performance', url_name='employee-performance')
    def performance(self, request, pk=None):
        employee = self.get_object()
        reviews = PerformanceReview.objects.filter(employee=employee).order_by('-created_at')
        return Response(PerformanceReviewSerializer(reviews, many=True).data)

# ======================================================
# BANK DETAILS
# ======================================================
class BankDetailsViewSet(viewsets.ModelViewSet):
    queryset = BankDetails.objects.select_related('employee')
    serializer_class = BankDetailsSerializer

    def get_permissions(self):
        return hr_permissions(self)

    def get_queryset(self):
        owner_ids = get_owner_ids(self.request.user)
        qs        = super().get_queryset().filter(employee__created_by__in=owner_ids)
        employee  = self.request.query_params.get('employee')
        if employee:
            qs = qs.filter(employee_id=employee)
        return qs

# ======================================================
# EMERGENCY CONTACT
# ======================================================
class EmergencyContactViewSet(viewsets.ModelViewSet):
    queryset = EmergencyContact.objects.select_related('employee')
    serializer_class = EmergencyContactSerializer

    def get_permissions(self):
        return hr_permissions(self)

    def get_queryset(self):
        owner_ids    = get_owner_ids(self.request.user)
        qs           = super().get_queryset().filter(employee__created_by__in=owner_ids)
        employee     = self.request.query_params.get('employee')
        contact_type = self.request.query_params.get('type')
        if employee:
            qs = qs.filter(employee_id=employee)
        if contact_type:
            qs = qs.filter(contact_type=contact_type)
        return qs

    def perform_create(self, serializer):
        employee_id = self.request.data.get('employee_id')
        employee    = get_object_or_404(Employee, pk=employee_id)
        serializer.save(employee=employee)

# ======================================================
# FAMILY MEMBER
# ======================================================
class FamilyMemberViewSet(viewsets.ModelViewSet):
    queryset = FamilyMember.objects.select_related('employee')
    serializer_class = FamilyMemberSerializer

    def get_permissions(self):
        return hr_permissions(self)

    def get_queryset(self):
        owner_ids = get_owner_ids(self.request.user)
        qs        = super().get_queryset().filter(employee__created_by__in=owner_ids)
        employee  = self.request.query_params.get('employee')
        if employee:
            qs = qs.filter(employee_id=employee)
        return qs

    def perform_create(self, serializer):
        employee_id = self.request.data.get('employee_id')
        employee    = get_object_or_404(Employee, pk=employee_id)
        serializer.save(employee=employee)

# ======================================================
# EDUCATION
# ======================================================
class EducationViewSet(viewsets.ModelViewSet):
    queryset = Education.objects.select_related('employee')
    serializer_class = EducationSerializer

    def get_permissions(self):
        return hr_permissions(self)

    def get_queryset(self):
        owner_ids = get_owner_ids(self.request.user)
        qs        = super().get_queryset().filter(employee__created_by__in=owner_ids)
        employee  = self.request.query_params.get('employee')
        if employee:
            qs = qs.filter(employee_id=employee)
        return qs

    def perform_create(self, serializer):
        employee_id = self.request.data.get('employee_id')
        employee    = get_object_or_404(Employee, pk=employee_id)
        serializer.save(employee=employee)

# ======================================================
# EXPERIENCE
# ======================================================
class ExperienceViewSet(viewsets.ModelViewSet):
    queryset = Experience.objects.select_related('employee')
    serializer_class = ExperienceSerializer

    def get_permissions(self):
        return hr_permissions(self)

    def get_queryset(self):
        owner_ids  = get_owner_ids(self.request.user)
        qs         = super().get_queryset().filter(employee__created_by__in=owner_ids)
        employee   = self.request.query_params.get('employee')
        is_current = self.request.query_params.get('current')
        if employee:
            qs = qs.filter(employee_id=employee)
        if is_current == 'true':
            qs = qs.filter(is_current=True)
        return qs

    def perform_create(self, serializer):
        employee_id = self.request.data.get('employee_id')
        employee    = get_object_or_404(Employee, pk=employee_id)
        serializer.save(employee=employee)

# ======================================================
# PROJECT
# ======================================================
class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.prefetch_related('tasks', 'members').select_related('lead')
    serializer_class = ProjectSerializer

    def get_permissions(self):
        return hr_permissions(self)

    def get_queryset(self):
        owner_ids = get_owner_ids(self.request.user)
        qs        = super().get_queryset().filter(created_by__in=owner_ids)
        lead      = self.request.query_params.get('lead')
        member    = self.request.query_params.get('member')
        color     = self.request.query_params.get('color')
        if lead:
            qs = qs.filter(lead_id=lead)
        if member:
            qs = qs.filter(members__id=member)
        if color:
            qs = qs.filter(color=color)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['get', 'post'], url_path='tasks', url_name='tasks')
    def tasks(self, request, pk=None):
        project = self.get_object()
        if request.method == 'GET':
            return Response(TaskSerializer(project.tasks.all(), many=True).data)
        serializer = TaskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(project=project)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='add-member', url_name='add-member')
    def add_member(self, request, pk=None):
        project     = self.get_object()
        employee_id = request.data.get('employee_id')
        employee    = get_object_or_404(Employee, pk=employee_id)
        project.members.add(employee)
        return Response({'detail': f'{employee.full_name} added to {project.title}.'})

# ======================================================
# TASK
# ======================================================
class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.select_related('project', 'assigned_to')
    serializer_class = TaskSerializer

    def get_permissions(self):
        return hr_permissions(self)

    def get_queryset(self):
        owner_ids   = get_owner_ids(self.request.user)
        qs          = super().get_queryset().filter(project__created_by__in=owner_ids)
        project     = self.request.query_params.get('project')
        assigned_to = self.request.query_params.get('assigned_to')
        completed   = self.request.query_params.get('completed')
        if project:
            qs = qs.filter(project_id=project)
        if assigned_to:
            qs = qs.filter(assigned_to_id=assigned_to)
        if completed is not None:
            qs = qs.filter(is_completed=(completed.lower() == 'true'))
        return qs

# ======================================================
# ASSET
# ======================================================
class AssetViewSet(viewsets.ModelViewSet):
    queryset = Asset.objects.select_related('assigned_to', 'assigned_by')
    serializer_class = AssetSerializer

    def get_permissions(self):
        return hr_permissions(self)

    def get_queryset(self):
        owner_ids   = get_owner_ids(self.request.user)
        qs          = super().get_queryset().filter(assigned_to__created_by__in=owner_ids)
        assigned_to = self.request.query_params.get('assigned_to')
        assigned_by = self.request.query_params.get('assigned_by')
        if assigned_to:
            qs = qs.filter(assigned_to_id=assigned_to)
        if assigned_by:
            qs = qs.filter(assigned_by_id=assigned_by)
        return qs

    # 👇 YE NAYA METHOD ADD KAREIN
    def perform_create(self, serializer):
        assigned_by_employee = None
        try:
            assigned_by_employee = Employee.objects.get(user=self.request.user)
        except Employee.DoesNotExist:
            pass
        serializer.save(assigned_by=assigned_by_employee)
# ======================================================
# ATTENDANCE
# ======================================================
class AttendanceViewSet(viewsets.ModelViewSet):
    queryset = Attendance.objects.all().order_by('-date')
    serializer_class = AttendanceSerializer

    def get_permissions(self):
        if self.action in ('checkin', 'checkout', 'today_record', 'weekly'):
            return [can('hr', 'view')()]
        return hr_permissions(self)

    def get_queryset(self):
        owner_ids    = get_owner_ids(self.request.user)
        qs           = super().get_queryset().filter(employee__created_by__in=owner_ids)
        employee     = self.request.query_params.get('employee')
        date_param   = self.request.query_params.get('date')
        status_param = self.request.query_params.get('status')
        if employee:
            qs = qs.filter(employee_id=employee)
        if date_param:
            qs = qs.filter(date=date_param)
        if status_param:
            qs = qs.filter(status=status_param)
        return qs

    @action(detail=False, methods=['get'], url_path='stats', url_name='stats')
    def stats(self, request):
        owner_ids = get_owner_ids(request.user)
        today     = date.today()
        today_qs  = Attendance.objects.filter(date=today, employee__created_by__in=owner_ids)
        return Response({
            'total_employees': Employee.objects.filter(created_by__in=owner_ids).count(),
            'late_today':      today_qs.filter(late__gt=0).count(),
            'unauthorized':    today_qs.filter(status='Absent').count(),
            'permissions':     today_qs.filter(status='Leave').count(),
            'absent':          today_qs.filter(status='Absent').count(),
        })

    @action(detail=False, methods=['get'], url_path='weekly', url_name='weekly')
    def weekly(self, request):
        employee_id = request.query_params.get('employee')
        if not employee_id:
            return Response({'detail': 'employee param required.'}, status=400)

        import uuid as uuid_module
        try:
            uuid_module.UUID(str(employee_id))
        except ValueError:
            return Response(
                {'detail': f'"{employee_id}" is not a valid UUID.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        owner_ids  = get_owner_ids(request.user)
        today      = date.today()
        week_start = today - timedelta(days=today.weekday())
        days       = [week_start + timedelta(days=i) for i in range(5)]

        records = {
            r.date: r
            for r in Attendance.objects.filter(
                employee_id=employee_id,
                date__range=(week_start, today),
                employee__created_by__in=owner_ids
            )
        }

        day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
        result = []
        for i, d in enumerate(days):
            rec   = records.get(d)
            hours = float(rec.production_hours) if rec and rec.production_hours else 0
            result.append({'day': day_names[i], 'hours': hours})
        return Response(result)

    @action(detail=False, methods=['get'], url_path='today', url_name='today')
    def today_record(self, request):
        employee_id = request.query_params.get('employee')
        if not employee_id:
            return Response({'detail': 'employee param required.'}, status=400)

        import uuid as uuid_module
        try:
            uuid_module.UUID(str(employee_id))
        except ValueError:
            return Response(
                {'detail': f'"{employee_id}" is not a valid UUID.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        owner_ids = get_owner_ids(request.user)
        try:
            record = Attendance.objects.get(
                employee_id=employee_id,
                date=date.today(),
                employee__created_by__in=owner_ids
            )
            return Response(AttendanceSerializer(record).data)
        except Attendance.DoesNotExist:
            return Response(None)

    @action(detail=False, methods=['post'], url_path='checkin', url_name='checkin')
    def checkin(self, request):
        employee_id = request.data.get('employee')
        if not employee_id:
            return Response(
                {'detail': 'employee field is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        import uuid as uuid_module
        try:
            uuid_module.UUID(str(employee_id))
        except ValueError:
            return Response(
                {'detail': f'"{employee_id}" is not a valid UUID.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        owner_ids = get_owner_ids(request.user)
        employee  = get_object_or_404(Employee, pk=employee_id, created_by__in=owner_ids)
        today     = date.today()
        now_time  = datetime.now().time().replace(second=0, microsecond=0)

        record, created = Attendance.objects.get_or_create(
            employee=employee,
            date=today,
            defaults={
                'status':   'Present',
                'check_in': now_time,
            },
        )

        if not created:
            if record.check_in:
                return Response(AttendanceSerializer(record).data, status=status.HTTP_200_OK)
            record.check_in = now_time
            record.status   = 'Present'
            record.save(update_fields=['check_in', 'status'])

        return Response(
            AttendanceSerializer(record).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=False, methods=['patch'], url_path='checkout', url_name='checkout')
    def checkout(self, request):
        employee_id = request.data.get('employee')
        if not employee_id:
            return Response(
                {'detail': 'employee field is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        import uuid as uuid_module
        try:
            uuid_module.UUID(str(employee_id))
        except ValueError:
            return Response(
                {'detail': f'"{employee_id}" is not a valid UUID.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        owner_ids = get_owner_ids(request.user)
        today     = date.today()
        try:
            record = Attendance.objects.get(
                employee_id=employee_id,
                date=today,
                employee__created_by__in=owner_ids
            )
        except Attendance.DoesNotExist:
            return Response(
                {'detail': 'No check-in record for today. Please check in first.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not record.check_in:
            return Response(
                {'detail': 'Employee has not checked in today.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if record.check_out:
            return Response(AttendanceSerializer(record).data, status=status.HTTP_200_OK)

        now_time     = datetime.now().time().replace(second=0, microsecond=0)
        check_in_dt  = datetime.combine(today, record.check_in)
        check_out_dt = datetime.combine(today, now_time)

        total_secs   = (check_out_dt - check_in_dt).total_seconds()
        break_secs   = (record.break_time or 0) * 60
        prod_hours   = round(max(total_secs - break_secs, 0) / 3600, 2)

        record.check_out        = now_time
        record.production_hours = prod_hours
        record.save(update_fields=['check_out', 'production_hours'])

        return Response(AttendanceSerializer(record).data, status=status.HTTP_200_OK)

# ======================================================
# LEAVE
# ======================================================
class LeaveViewSet(viewsets.ModelViewSet):
    queryset = Leave.objects.all().order_by('-start_date')
    serializer_class = LeaveSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [can('hr', 'view')()]
        return hr_permissions(self)

    def get_queryset(self):
        owner_ids    = get_owner_ids(self.request.user)
        qs           = super().get_queryset().filter(employee__created_by__in=owner_ids)
        employee     = self.request.query_params.get('employee')
        status_param = self.request.query_params.get('status')
        leave_type   = self.request.query_params.get('leave_type')
        if employee:
            qs = qs.filter(employee_id=employee)
        if status_param:
            qs = qs.filter(status=status_param)
        if leave_type:
            qs = qs.filter(leave_type=leave_type)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

# ======================================================
# PAYROLL
# ======================================================
class PayrollViewSet(viewsets.ModelViewSet):
    queryset = Payroll.objects.all().order_by('-created_at')
    serializer_class = PayrollSerializer

    def get_permissions(self):
        return hr_permissions(self)

    def get_queryset(self):
        owner_ids   = get_owner_ids(self.request.user)
        qs          = super().get_queryset().filter(employee__created_by__in=owner_ids)
        employee_id = self.request.query_params.get('employee')
        month       = self.request.query_params.get('month')
        if employee_id:
            qs = qs.filter(employee_id=employee_id)
        if month:
            qs = qs.filter(month=month)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

# ======================================================
# PERFORMANCE REVIEW
# ======================================================
class PerformanceReviewViewSet(viewsets.ModelViewSet):
    queryset = PerformanceReview.objects.all().order_by('-created_at')
    serializer_class = PerformanceReviewSerializer

    def get_permissions(self):
        return hr_permissions(self)

    def get_queryset(self):
        owner_ids    = get_owner_ids(self.request.user)
        qs           = super().get_queryset().filter(employee__created_by__in=owner_ids)
        employee     = self.request.query_params.get('employee')
        reviewer     = self.request.query_params.get('reviewer')
        status_param = self.request.query_params.get('status')
        month        = self.request.query_params.get('month')
        if employee:
            qs = qs.filter(employee_id=employee)
        if reviewer:
            qs = qs.filter(reviewer_id=reviewer)
        if status_param:
            qs = qs.filter(status=status_param)
        if month:
            qs = qs.filter(month__icontains=month)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

# ======================================================
# JOB POST
# ======================================================
class JobPostViewSet(viewsets.ModelViewSet):
    queryset = JobPost.objects.all().order_by('-posted_date')
    serializer_class = JobPostSerializer

    def get_permissions(self):
        return hr_permissions(self)

    def get_queryset(self):
        owner_ids    = get_owner_ids(self.request.user)
        qs           = super().get_queryset().filter(created_by__in=owner_ids)
        status_param = self.request.query_params.get('status')
        job_type     = self.request.query_params.get('job_type')
        company      = self.request.query_params.get('company')
        if status_param:
            qs = qs.filter(status=status_param)
        if job_type:
            qs = qs.filter(job_type=job_type)
        if company:
            qs = qs.filter(company__icontains=company)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

# ======================================================
# CANDIDATE
# ======================================================
class CandidateViewSet(viewsets.ModelViewSet):
    queryset = Candidate.objects.all().order_by('-applied_date')
    serializer_class = CandidateSerializer

    def get_permissions(self):
        return hr_permissions(self)

    def get_queryset(self):
        owner_ids    = get_owner_ids(self.request.user)
        qs           = super().get_queryset().filter(created_by__in=owner_ids)
        status_param = self.request.query_params.get('status')
        job_post     = self.request.query_params.get('job_post')
        if status_param:
            qs = qs.filter(status=status_param)
        if job_post:
            qs = qs.filter(job_post_id=job_post)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

# ======================================================
# PROMOTION
# ======================================================
class PromotionViewSet(viewsets.ModelViewSet):
    queryset = Promotion.objects.all().order_by('-promotion_date')
    serializer_class = PromotionSerializer

    def get_permissions(self):
        return hr_permissions(self)

    def get_queryset(self):
        owner_ids  = get_owner_ids(self.request.user)
        qs         = super().get_queryset().filter(employee__created_by__in=owner_ids)
        employee   = self.request.query_params.get('employee')
        department = self.request.query_params.get('department')
        date_param = self.request.query_params.get('date')
        if employee:
            qs = qs.filter(employee_id=employee)
        if department:
            qs = qs.filter(department_id=department)
        if date_param:
            qs = qs.filter(promotion_date=date_param)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

# ======================================================
# RESIGNATION
# ======================================================
class ResignationViewSet(viewsets.ModelViewSet):
    queryset = Resignation.objects.all().order_by('-resignation_date')
    serializer_class = ResignationSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [can('hr', 'view')()]
        return hr_permissions(self)

    def get_queryset(self):
        owner_ids  = get_owner_ids(self.request.user)
        qs         = super().get_queryset().filter(employee__created_by__in=owner_ids)
        employee   = self.request.query_params.get('employee')
        department = self.request.query_params.get('department')
        reason     = self.request.query_params.get('reason')
        if employee:
            qs = qs.filter(employee_id=employee)
        if department:
            qs = qs.filter(department_id=department)
        if reason:
            qs = qs.filter(reason=reason)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

# ======================================================
# TERMINATION
# ======================================================
class TerminationViewSet(viewsets.ModelViewSet):
    queryset = Termination.objects.prefetch_related(
        'reinstatements'
    ).all().order_by('-termination_date')
    serializer_class = TerminationSerializer

    def get_permissions(self):
        return hr_permissions(self)

    def get_queryset(self):
        owner_ids        = get_owner_ids(self.request.user)
        qs               = super().get_queryset().filter(employee__created_by__in=owner_ids)
        employee         = self.request.query_params.get('employee')
        department       = self.request.query_params.get('department')
        termination_type = self.request.query_params.get('type')
        if employee:
            qs = qs.filter(employee_id=employee)
        if department:
            qs = qs.filter(department_id=department)
        if termination_type:
            qs = qs.filter(termination_type=termination_type)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(
        detail=True,
        methods=['get', 'post'],
        url_path='reinstatements',
        url_name='reinstatements',
    )
    def reinstatements(self, request, pk=None):
        termination = self.get_object()
        if request.method == 'GET':
            qs = TerminationReinstatement.objects.filter(termination=termination)
            serializer = TerminationReinstatementSerializer(qs, many=True)
            return Response(serializer.data)

        serializer = TerminationReinstatementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(termination=termination)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=['patch'],
        url_path=r'reinstatements/(?P<r_id>\d+)',
        url_name='reinstatement-detail',
    )
    def reinstatement_detail(self, request, pk=None, r_id=None):
        termination = self.get_object()
        instance    = get_object_or_404(
            TerminationReinstatement, pk=r_id, termination=termination
        )
        serializer = TerminationReinstatementSerializer(
            instance, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(
        detail=True,
        methods=['get'],
        url_path='history',
        url_name='history',
    )
    def history(self, request, pk=None):
        termination = self.get_object()
        log = [
            {
                'action':    'Termination record created',
                'note':      '',
                'timestamp': termination.created_at,
            }
        ]
        return Response(log)

# ======================================================
# JWT AUTH
# ======================================================
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
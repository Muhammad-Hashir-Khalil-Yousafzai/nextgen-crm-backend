from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
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


# ================= DEPARTMENT =================
class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'name', 'employees', 'status', 'created_at']


# ================= DESIGNATION =================
class DesignationSerializer(serializers.ModelSerializer):
    employees = serializers.SerializerMethodField()
    department_name = serializers.CharField(source='department.name', read_only=True)
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        source='department',
        write_only=True,
        required=False,
        allow_null=True
    )

    class Meta:
        model = Designation
        fields = [
            'id', 'title', 'department_name', 'department_id',
            'level', 'status', 'employees', 'created_at',
        ]
        read_only_fields = ['id', 'employees', 'created_at']

    def get_employees(self, obj):
        return obj.employees


# ================= BANK DETAILS =================
class BankDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankDetails
        fields = ['id', 'bank_name', 'account_no', 'ifsc_code', 'branch', 'updated_at']


# ================= EMERGENCY CONTACT =================
class EmergencyContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmergencyContact
        fields = ['id', 'contact_type', 'name', 'relation', 'phone1', 'phone2']


# ================= FAMILY MEMBER =================
class FamilyMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = FamilyMember
        fields = ['id', 'name', 'relationship', 'email', 'phone']


# ================= EDUCATION =================
class EducationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Education
        fields = ['id', 'institution', 'degree', 'start_year', 'end_year']


# ================= EXPERIENCE =================
class ExperienceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Experience
        fields = ['id', 'company', 'position', 'start_date', 'end_date', 'is_current']


# ================= TASK =================
class TaskSerializer(serializers.ModelSerializer):
    assigned_to_name = serializers.CharField(
        source='assigned_to.full_name', read_only=True
    )

    class Meta:
        model = Task
        fields = ['id', 'title', 'assigned_to', 'assigned_to_name', 'is_completed', 'due_date']


# ================= PROJECT =================
class ProjectSerializer(serializers.ModelSerializer):
    task_count = serializers.ReadOnlyField()
    completed_task_count = serializers.ReadOnlyField()
    tasks = TaskSerializer(many=True, read_only=True)
    lead_name = serializers.CharField(source='lead.full_name', read_only=True)

    class Meta:
        model = Project
        fields = [
            'id', 'title', 'deadline', 'color',
            'lead', 'lead_name',
            'task_count', 'completed_task_count', 'tasks',
            'created_at',
        ]


# ================= ASSET =================
class AssetSerializer(serializers.ModelSerializer):
    assigned_to_name = serializers.CharField(
        source='assigned_to.full_name', read_only=True
    )
    assigned_by_name = serializers.CharField(
        source='assigned_by.full_name', read_only=True
    )

    class Meta:
        model = Asset
        fields = [
            'id', 'asset_id', 'name', 'icon',
            'assigned_to', 'assigned_to_name',
            'assigned_by', 'assigned_by_name',
            'assigned_date',
        ]


# ================= EMPLOYEE (list) =================
class EmployeeListSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()
    department = DepartmentSerializer(read_only=True)
    designation = DesignationSerializer(read_only=True)
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(), source='department',
        write_only=True, required=False
    )
    designation_id = serializers.PrimaryKeyRelatedField(
        queryset=Designation.objects.all(), source='designation',
        write_only=True, required=False
    )
    password = serializers.CharField(write_only=True, required=False, default='Employee@123')

    class Meta:
        model = Employee
        fields = [
            'id', 'employee_id', 'full_name', 'name', 'first_name', 'last_name',
            'email', 'phone', 'avatar', 'role', 'team', 'report_office',
            'department', 'department_id', 'designation', 'designation_id',
            'joining_date', 'salary', 'status',
            'gender', 'birthday', 'address',
            'passport_no', 'passport_exp_date', 'nationality',
            'religion', 'marital_status', 'employment_of_spouse',
            'created_at', 'password',
        ]

# Keep old name as alias so existing imports don't break
EmployeeSerializer = EmployeeListSerializer


# ================= EMPLOYEE (full detail — nested) =================
class EmployeeDetailSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()
    department = DepartmentSerializer(read_only=True)
    designation = DesignationSerializer(read_only=True)

    bank_details = BankDetailsSerializer(read_only=True)
    emergency_contacts = EmergencyContactSerializer(many=True, read_only=True)
    family_members = FamilyMemberSerializer(many=True, read_only=True)
    educations = EducationSerializer(many=True, read_only=True)
    experiences = ExperienceSerializer(many=True, read_only=True)
    assets = AssetSerializer(many=True, read_only=True)
    performance_reviews = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = [
            'id', 'employee_id', 'full_name', 'name', 'first_name', 'last_name',
            'email', 'phone', 'avatar', 'role', 'team', 'report_office',
            'gender', 'birthday', 'address',
            'passport_no', 'passport_exp_date', 'nationality',
            'religion', 'marital_status', 'employment_of_spouse',
            'department', 'designation',
            'joining_date', 'salary', 'status',
            'bank_details', 'emergency_contacts', 'family_members',
            'educations', 'experiences', 'assets', 'performance_reviews',
            'created_at',
        ]

    def get_performance_reviews(self, obj):
        from .serializers import PerformanceReviewSerializer
        reviews = obj.performance_reviews.all()[:5]
        return PerformanceReviewSerializer(reviews, many=True).data


# ================= ATTENDANCE =================
class AttendanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.name', read_only=True)
    employee_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(), source='employee', write_only=True
    )
    check_in_display = serializers.SerializerMethodField()
    check_out_display = serializers.SerializerMethodField()
    break_time_display = serializers.SerializerMethodField()
    late_display = serializers.SerializerMethodField()
    desk_display = serializers.SerializerMethodField()
    overtime_display = serializers.SerializerMethodField()
    production_hours_display = serializers.SerializerMethodField()
    total_hours = serializers.SerializerMethodField()

    class Meta:
        model = Attendance
        fields = [
            'id', 'employee_id', 'employee_name',
            'date', 'status',
            'check_in', 'check_out',
            'break_time', 'late', 'desk', 'overtime', 'production_hours',
            'check_in_display', 'check_out_display',
            'break_time_display', 'late_display',
            'desk_display', 'overtime_display',
            'production_hours_display', 'total_hours',
            'created_at', 'updated_at',
        ]

    def _format_time(self, t):
        return t.strftime('%I:%M %p') if t else None

    def _format_minutes(self, value):
        return f"{value} Min" if value is not None else None

    def get_check_in_display(self, obj):       return self._format_time(obj.check_in)
    def get_check_out_display(self, obj):      return self._format_time(obj.check_out)
    def get_break_time_display(self, obj):     return self._format_minutes(obj.break_time)
    def get_late_display(self, obj):           return self._format_minutes(obj.late)
    def get_desk_display(self, obj):           return self._format_minutes(obj.desk)
    def get_overtime_display(self, obj):       return self._format_minutes(obj.overtime)
    def get_production_hours_display(self, obj):
        return f"{obj.production_hours} Hrs" if obj.production_hours is not None else None
    def get_total_hours(self, obj):            return obj.total_hours


# ================= LEAVE =================
class LeaveSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.name', read_only=True)
    employee_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(), source='employee', write_only=True
    )
    approved_by_name = serializers.CharField(default="Pending Approval")
    approved_by_role = serializers.CharField(default="Pending")
    approved_by_avatar = serializers.CharField(
        default="https://api.dicebear.com/7.x/avataaars/svg?seed=pending"
    )

    class Meta:
        model = Leave
        fields = [
            'id', 'employee_id', 'employee_name',
            'leave_type', 'badge',
            'start_date', 'end_date', 'total_days',
            'reason', 'status',
            'approved_by_name', 'approved_by_role', 'approved_by_avatar',
            'created_at', 'updated_at',
        ]


# ================= PAYROLL =================
class PayrollSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.name', read_only=True)
    employee_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(), source='employee', write_only=True
    )

    class Meta:
        model = Payroll
        fields = [
            'id', 'employee_id', 'employee_name',
            'month', 'basic_salary', 'allowances', 'deductions', 'net_salary',
            'created_at',
        ]


# ================= PERFORMANCE REVIEW =================
class PerformanceReviewSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.name', read_only=True)
    reviewer_name = serializers.CharField(source='reviewer.name', read_only=True)
    employee_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(), source='employee', write_only=True
    )
    reviewer_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(), source='reviewer',
        write_only=True, required=False, allow_null=True
    )

    class Meta:
        model = PerformanceReview
        fields = [
            'id', 'employee_id', 'employee_name',
            'reviewer_id', 'reviewer_name',
            'role', 'score', 'rating',
            'status', 'month', 'review',
            'created_at', 'updated_at',
        ]


# ================= JOB POST =================
class JobPostSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobPost
        fields = '__all__'
        read_only_fields = ['created_by']  # Yeh add karna zaroori hai


# ================= CANDIDATE =================
class CandidateSerializer(serializers.ModelSerializer):
    job_post = JobPostSerializer(read_only=True)
    job_post_id = serializers.PrimaryKeyRelatedField(
        queryset=JobPost.objects.all(), source='job_post',
        write_only=True, required=False
    )

    class Meta:
        model = Candidate
        fields = [
            'id', 'candidate_id', 'name', 'email',
            'applied_role', 'applied_date', 'status',
            'avatar', 'resume_url',
            'job_post', 'job_post_id',
            'created_at', 'updated_at',
        ]


# ================= PROMOTION =================
class PromotionSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    designation_from_title = serializers.CharField(source='designation_from.title', read_only=True)
    designation_to_title = serializers.CharField(source='designation_to.title', read_only=True)
    avatar = serializers.SerializerMethodField()

    employee_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(), source='employee', write_only=True
    )
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(), source='department',
        write_only=True, required=False
    )
    designation_from_id = serializers.PrimaryKeyRelatedField(
        queryset=Designation.objects.all(), source='designation_from',
        write_only=True, required=False
    )
    designation_to_id = serializers.PrimaryKeyRelatedField(
        queryset=Designation.objects.all(), source='designation_to',
        write_only=True, required=False
    )

    class Meta:
        model = Promotion
        fields = [
            'id',
            'employee_id', 'employee_name',
            'department_id', 'department_name',
            'designation_from_id', 'designation_from_title',
            'designation_to_id', 'designation_to_title',
            'avatar', 'promotion_date', 'color',
            'created_at', 'updated_at',
        ]

    def get_avatar(self, obj):
        return obj.avatar


# ================= RESIGNATION =================
class ResignationSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    employee_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(), source='employee', write_only=True
    )
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(), source='department',
        write_only=True, required=False
    )

    class Meta:
        model = Resignation
        fields = [
            'id',
            'employee_id', 'employee_name',
            'department_id', 'department_name',
            'reason', 'notice_date', 'resignation_date',
            'created_at', 'updated_at',
        ]


# ================= TERMINATION REINSTATEMENT =================
class TerminationReinstatementSerializer(serializers.ModelSerializer):
    class Meta:
        model = TerminationReinstatement
        fields = [
            'id',
            'reinstated_date',
            'court_case_number',
            'notes',
            'salary_paid',
            'salary_paid_date',
            'created_at',
        ]


# ================= TERMINATION =================
class TerminationSerializer(serializers.ModelSerializer):
    employee_name    = serializers.CharField(source='employee.name', read_only=True)
    department_name  = serializers.CharField(source='department.name', read_only=True)
    avatar           = serializers.SerializerMethodField()
    is_reinstated    = serializers.SerializerMethodField()
    reinstatements   = TerminationReinstatementSerializer(many=True, read_only=True)

    employee_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(), source='employee', write_only=True
    )
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(), source='department',
        write_only=True, required=False
    )

    class Meta:
        model = Termination
        fields = [
            'id',
            'employee_id', 'employee_name',
            'department_id', 'department_name',
            'avatar', 'termination_type',
            'notice_date', 'reason', 'termination_date', 'color',
            'is_reinstated', 'reinstatements',
            'created_at', 'updated_at',
        ]

    def get_avatar(self, obj):
        return obj.avatar

    def get_is_reinstated(self, obj):
        return obj.reinstatements.exists()


# ================= JWT AUTH =================
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user

        # ── Resolve role slugs ──────────────────────────────────────────────
        # Try custom roles from user_roles relation (system roles module)
        roles = []
        try:
            roles = list(
                user.user_roles.filter(is_active=True)
                .values_list('role__slug', flat=True)
            )
        except Exception:
            pass

        # ── Determine primary role ──────────────────────────────────────────
        # Priority: is_superuser → is_staff → first custom role → 'employee'
        if user.is_superuser:
            primary_role = "superadmin"
        elif user.is_staff:
            primary_role = "admin"
        elif roles:
            primary_role = roles[0]
        else:
            primary_role = "employee"

        user_data = {
            "id":           user.id,
            "name":         user.username,
            "email":        user.email,
            "initials":     user.username[0].upper() if user.username else "U",
            "status":       "active",
            "is_superuser": user.is_superuser,
            "is_staff":     user.is_staff,
            "primary_role": primary_role,   # ← frontend isSuperAdmin() + isEmployee() use karta hai
            "role":         primary_role,   # ← alias for legacy checks
            "department":   None,
        }

        try:
            employee = Employee.objects.get(email=user.email)
            user_data["employee_id"]         = str(employee.id)
            user_data["employee_display_id"] = employee.employee_id
        except Employee.DoesNotExist:
            user_data["employee_id"]         = None
            user_data["employee_display_id"] = ""

        data['user']  = user_data
        data['roles'] = roles   # ← full list frontend localStorage mein store karta hai
        return data
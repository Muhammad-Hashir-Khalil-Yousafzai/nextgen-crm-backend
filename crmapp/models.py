import uuid
import datetime
from django.db import models
from django.conf import settings
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver


# ================= CRM FILE =================
class crmFile(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    file = models.FileField(upload_to='uploads/')
    message_encrypted = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_created')
    status = models.CharField(max_length=20, default='pending')

    def __str__(self):
        return f"{self.user} - {self.file}"


# ================= DEPARTMENT =================
class Department(models.Model):
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    employees = models.IntegerField(default=0)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Active')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_created')

    def __str__(self):
        return self.name


# ================= DESIGNATION =================
class Designation(models.Model):
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=100)

    department = models.ForeignKey(
        'Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="designations"
    )

    level = models.CharField(max_length=50, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Active')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_created')

    @property
    def employees(self):
        return self.designation_employees.filter(status='active').count()

    def __str__(self):
        return self.title


# ================= EMPLOYEE =================
class Employee(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('terminated', 'Terminated')
    ]
    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
        ('Other', 'Other'),
    ]
    MARITAL_CHOICES = [
        ('Yes', 'Married'),
        ('No', 'Single'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=100, blank=True)
    first_name = models.CharField(max_length=50, blank=True)
    last_name = models.CharField(max_length=50, blank=True)

    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    employee_id = models.CharField(max_length=20, unique=True)

    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="department_employees"
    )

    designation = models.ForeignKey(
        Designation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="designation_employees"
    )

    # ── Profile
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    role = models.CharField(max_length=100, blank=True)
    team = models.CharField(max_length=100, blank=True)
    report_office = models.CharField(max_length=100, blank=True)

    # ── Personal info
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    birthday = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True)
    passport_no = models.CharField(max_length=50, blank=True)
    passport_exp_date = models.DateField(null=True, blank=True)
    nationality = models.CharField(max_length=100, blank=True)
    religion = models.CharField(max_length=100, blank=True)
    marital_status = models.CharField(max_length=5, choices=MARITAL_CHOICES, blank=True)
    employment_of_spouse = models.BooleanField(default=False)

    joining_date = models.DateField(null=True, blank=True)
    salary = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_created')

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, blank=True,
        related_name="employee_profile"
    )

    @property
    def full_name(self):
        if self.first_name or self.last_name:
            return f"{self.first_name} {self.last_name}".strip()
        return self.name

    def __str__(self):
        return self.name or self.email


# ================= BANK DETAILS =================
class BankDetails(models.Model):
    employee = models.OneToOneField(
        Employee,
        on_delete=models.CASCADE,
        related_name="bank_details"
    )
    bank_name = models.CharField(max_length=150, blank=True)
    account_no = models.CharField(max_length=50, blank=True)
    ifsc_code = models.CharField(max_length=20, blank=True)
    branch = models.CharField(max_length=150, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Bank – {self.employee.full_name}"


# ================= EMERGENCY CONTACT =================
class EmergencyContact(models.Model):
    TYPE_CHOICES = [
        ('Primary', 'Primary'),
        ('Secondary', 'Secondary'),
    ]

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="emergency_contacts"
    )
    contact_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    name = models.CharField(max_length=150)
    relation = models.CharField(max_length=100)
    phone1 = models.CharField(max_length=30)
    phone2 = models.CharField(max_length=30, blank=True)

    class Meta:
        unique_together = ('employee', 'contact_type')

    def __str__(self):
        return f"{self.contact_type} – {self.name} ({self.employee.full_name})"


# ================= FAMILY MEMBER =================
class FamilyMember(models.Model):
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="family_members"
    )
    name = models.CharField(max_length=150)
    relationship = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)

    def __str__(self):
        return f"{self.name} ({self.relationship}) – {self.employee.full_name}"


# ================= EDUCATION =================
class Education(models.Model):
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="educations"
    )
    institution = models.CharField(max_length=200)
    degree = models.CharField(max_length=200)
    start_year = models.PositiveIntegerField(null=True, blank=True)
    end_year = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['-end_year']

    def __str__(self):
        return f"{self.degree} – {self.institution}"


# ================= EXPERIENCE =================
class Experience(models.Model):
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="experiences"
    )
    company = models.CharField(max_length=200)
    position = models.CharField(max_length=200)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)   # null = current job
    is_current = models.BooleanField(default=False)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.position} @ {self.company}"


# ================= PROJECT =================
class Project(models.Model):
    COLOR_CHOICES = [
        ('blue', 'Blue'),
        ('purple', 'Purple'),
        ('green', 'Green'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    deadline = models.DateField(null=True, blank=True)
    color = models.CharField(max_length=10, choices=COLOR_CHOICES, default='blue')
    lead = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="led_projects"
    )
    members = models.ManyToManyField(
        Employee,
        related_name="projects",
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_created')

    @property
    def task_count(self):
        return self.tasks.count()

    @property
    def completed_task_count(self):
        return self.tasks.filter(is_completed=True).count()

    def __str__(self):
        return self.title


# ================= TASK =================
class Task(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="tasks"
    )
    title = models.CharField(max_length=200)
    assigned_to = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="tasks"
    )
    is_completed = models.BooleanField(default=False)
    due_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.title


# ================= ASSET =================
class Asset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset_id = models.CharField(max_length=30, unique=True)   # e.g. "AST-001"
    name = models.CharField(max_length=200)
    icon = models.CharField(max_length=10, blank=True)        # emoji
    assigned_to = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="assets"
    )
    assigned_by = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="assets_assigned"
    )
    assigned_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.asset_id})"


# ================= ATTENDANCE =================
class Attendance(models.Model):
    STATUS_CHOICES = [
        ('Present', 'Present'),
        ('Absent', 'Absent'),
        ('Late', 'Late'),
        ('Leave', 'Leave'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="attendance"
    )

    date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    check_in = models.TimeField(null=True, blank=True)
    check_out = models.TimeField(null=True, blank=True)
    break_time = models.IntegerField(null=True, blank=True, help_text="Break duration in minutes")
    late = models.IntegerField(null=True, blank=True, help_text="Late duration in minutes")
    desk = models.IntegerField(null=True, blank=True, help_text="Desk time in minutes")
    overtime = models.IntegerField(null=True, blank=True, help_text="Overtime in minutes")
    production_hours = models.DecimalField(
        max_digits=4, decimal_places=2,
        null=True, blank=True,
        help_text="Production hours as decimal e.g. 8.2"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_created')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('employee', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"{self.employee.name} - {self.date} - {self.status}"

    @property
    def total_hours(self):
        if self.check_in and self.check_out:
            today = datetime.date.today()
            start = datetime.datetime.combine(today, self.check_in)
            end = datetime.datetime.combine(today, self.check_out)
            diff = end - start
            return round(diff.seconds / 3600, 2)
        return None


# ================= LEAVE =================
class Leave(models.Model):
    STATUS_CHOICES = [
        ('New', 'New'),
        ('Approved', 'Approved'),
        ('Cancelled', 'Cancelled'),
        ('Rejected', 'Rejected'),
    ]
    LEAVE_TYPE_CHOICES = [
        ('Annual Leave', 'Annual Leave'),
        ('Medical Leave', 'Medical Leave'),
        ('Casual Leave', 'Casual Leave'),
        ('Other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="leaves"
    )

    leave_type = models.CharField(max_length=50, choices=LEAVE_TYPE_CHOICES)
    badge = models.CharField(max_length=10, blank=True, null=True)
    start_date = models.DateField()
    end_date = models.DateField()
    total_days = models.IntegerField()
    reason = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='New')

    approved_by_name = models.CharField(max_length=100, blank=True, default="Pending Approval")
    approved_by_role = models.CharField(max_length=50, blank=True, default="Pending")
    approved_by_avatar = models.CharField(
        max_length=255,
        blank=True,
        default="https://api.dicebear.com/7.x/avataaars/svg?seed=pending",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_created')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.employee.name} - {self.leave_type} - {self.status}"


# ================= PERFORMANCE REVIEW =================
class PerformanceReview(models.Model):
    STATUS_CHOICES = [
        ('Excellent', 'Excellent'),
        ('Good', 'Good'),
        ('Average', 'Average'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="performance_reviews"
    )
    reviewer = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviews_given'
    )

    role = models.CharField(max_length=100, blank=True, null=True)
    score = models.IntegerField(null=True, blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Good')
    month = models.CharField(max_length=20, null=True, blank=True)
    review = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_created')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.employee.name} - {self.status} - {self.month}"


# ================= PAYROLL =================
class Payroll(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="payrolls"
    )

    month = models.CharField(max_length=20)
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2)
    allowances = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_salary = models.DecimalField(max_digits=12, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_created')

    def __str__(self):
        return f"{self.employee.name} - {self.month} - {self.net_salary}"


# ================= JOB POST =================
class JobPost(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('filled', 'Filled'),
        ('expired', 'Expired'),
    ]
    JOB_TYPE_CHOICES = [
        ('Full-Time', 'Full-Time'),
        ('Part-Time', 'Part-Time'),
        ('Contract', 'Contract'),
        ('Internship', 'Internship'),
        ('Remote', 'Remote'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    company = models.CharField(max_length=200)
    location = models.CharField(max_length=200)
    salary = models.CharField(max_length=100, blank=True, null=True)
    experience = models.CharField(max_length=100, blank=True, null=True)
    job_type = models.CharField(max_length=50, choices=JOB_TYPE_CHOICES, default='Full-Time')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    applicants = models.IntegerField(default=0)
    color = models.CharField(max_length=10, blank=True, null=True)
    posted_date = models.DateField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_created')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-posted_date']
        verbose_name = 'Job Post'
        verbose_name_plural = 'Job Posts'

    def __str__(self):
        return f"{self.title} @ {self.company}"


# ================= CANDIDATE =================
class Candidate(models.Model):
    STATUS_CHOICES = [
        ('New', 'New'),
        ('Scheduled', 'Scheduled'),
        ('Interviewed', 'Interviewed'),
        ('Offered', 'Offered'),
        ('Hired', 'Hired'),
        ('Rejected', 'Rejected'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate_id = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    applied_role = models.CharField(max_length=100)
    applied_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='New')
    avatar = models.ImageField(upload_to='candidates/avatars/', null=True, blank=True)
    resume_url = models.FileField(upload_to='candidates/resumes/', null=True, blank=True)

    job_post = models.ForeignKey(
        JobPost,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='candidates'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='candidates')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.candidate_id} - {self.name}"


# ================= PROMOTION =================
class Promotion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="promotions"
    )
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="promotions"
    )
    designation_from = models.ForeignKey(
        Designation, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="promoted_from"
    )
    designation_to = models.ForeignKey(
        Designation, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="promoted_to"
    )

    promotion_date = models.DateField()
    color = models.CharField(max_length=10, blank=True, null=True, default="#8b5cf6")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_created')
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def avatar(self):
        fn = self.employee.first_name[:1] if self.employee.first_name else ''
        ln = self.employee.last_name[:1] if self.employee.last_name else ''
        return (fn + ln).upper() or self.employee.name[:2].upper()

    class Meta:
        ordering = ['-promotion_date']

    def __str__(self):
        return f"{self.employee.name} promoted on {self.promotion_date}"


# ================= RESIGNATION =================
class Resignation(models.Model):
    REASON_CHOICES = [
        ('Career Change', 'Career Change'),
        ('Entrepreneurial Pursuits', 'Entrepreneurial Pursuits'),
        ('Relocation', 'Relocation'),
        ('Health Reasons', 'Health Reasons'),
        ('Personal Development', 'Personal Development'),
        ('Better Opportunity', 'Better Opportunity'),
        ('Family Reasons', 'Family Reasons'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="resignations"
    )
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="resignations"
    )

    reason = models.CharField(max_length=100, choices=REASON_CHOICES)
    notice_date = models.DateField()
    resignation_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_created')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-resignation_date']

    def __str__(self):
        return f"{self.employee.name} - {self.reason} - {self.resignation_date}"


# ================= TERMINATION =================
class Termination(models.Model):
    TERMINATION_TYPE_CHOICES = [
        ('Retirement', 'Retirement'),
        ('Insubordination', 'Insubordination'),
        ('Layoff', 'Layoff'),
        ('Breach of Contract', 'Breach of Contract'),
        ('Lack of Skills', 'Lack of Skills'),
        ('Voluntary Resignation', 'Voluntary Resignation'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="terminations"
    )
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="terminations"
    )

    termination_type = models.CharField(max_length=50, choices=TERMINATION_TYPE_CHOICES)
    notice_date = models.DateField()
    reason = models.TextField()
    termination_date = models.DateField()
    color = models.CharField(max_length=10, blank=True, null=True, default="#8b5cf6")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_created')
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def avatar(self):
        fn = self.employee.first_name[:1] if self.employee.first_name else ''
        ln = self.employee.last_name[:1] if self.employee.last_name else ''
        return (fn + ln).upper() or self.employee.name[:2].upper()

    class Meta:
        ordering = ['-termination_date']

    def __str__(self):
        return f"{self.employee.name} - {self.termination_type} - {self.termination_date}"\
# models.py mein sirf yeh class add karo existing Termination model ke BAAD:

class TerminationReinstatement(models.Model):
    termination = models.ForeignKey(
        Termination,
        on_delete=models.CASCADE,
        related_name="reinstatements"
    )
    reinstated_date   = models.DateField()
    court_case_number = models.CharField(max_length=100, blank=True, default="")
    notes             = models.TextField(blank=True, default="")
    salary_paid       = models.BooleanField(default=False)
    salary_paid_date  = models.DateField(null=True, blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-reinstated_date"]

    def __str__(self):
        return f"Reinstatement for {self.termination.employee} on {self.reinstated_date}"
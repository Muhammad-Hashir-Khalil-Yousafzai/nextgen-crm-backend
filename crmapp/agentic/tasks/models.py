from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid
from crmapp.agentic.core.models import Resource  # ← re-export so nothing breaks


def make_task_id():
    return f"tsk-{uuid.uuid4().hex[:6]}"

def make_dep_id():
    return f"dep-{uuid.uuid4().hex[:6]}"

def make_goal_id():
    return f"goal-{uuid.uuid4().hex[:6]}"

def make_tmpl_id():
    return f"tmpl-{uuid.uuid4().hex[:6]}"

def make_hist_id():
    return f"hist-{uuid.uuid4().hex[:6]}"

def make_res_id():
    return f"res-{uuid.uuid4().hex[:6]}"

def make_alert_id():
    return f"alert-{uuid.uuid4().hex[:6]}"

def make_perf_id():
    return f"perf-{uuid.uuid4().hex[:6]}"


class Task(models.Model):
    STATUS_CHOICES = [
        ('running', 'Running'),
        ('pending', 'Pending'),
        ('scheduled', 'Scheduled'),
        ('blocked', 'Blocked'),
        ('completed', 'Completed'),
        ('idle', 'Idle'),
        ('failed', 'Failed'),
    ]
    PRIORITY_CHOICES = [
        ('critical', 'Critical'),
        ('high', 'High'),
        ('normal', 'Normal'),
        ('low', 'Low'),
    ]
    EXECUTION_MODE_CHOICES = [
        ('sequential', 'Sequential'),
        ('parallel', 'Parallel'),
    ]
    DEPT_CHOICES = [
        ('Sales', 'Sales'),
        ('Finance', 'Finance'),
        ('Support', 'Support'),
        ('CRM', 'CRM'),
        ('Marketing', 'Marketing'),
        ('Analytics', 'Analytics'),
        ('HR', 'HR'),
    ]

    id = models.CharField(max_length=50, primary_key=True, default=make_task_id)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal')
    assignee = models.CharField(max_length=100, blank=True, null=True)
    dept = models.CharField(max_length=50, choices=DEPT_CHOICES)
    depends_on = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='dependent_tasks')
    schedule = models.CharField(max_length=100, default='On trigger')
    scheduled_at = models.DateTimeField(null=True, blank=True, db_index=True)
    deadline = models.DateField(null=True, blank=True)
    progress = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    parallel_execution = models.BooleanField(default=False)
    exec_mode = models.CharField(max_length=20, choices=EXECUTION_MODE_CHOICES, default='sequential')
    conditions = models.JSONField(default=list, blank=True)
    estimated_steps = models.IntegerField(default=1)
    actual_duration_ms = models.IntegerField(null=True, blank=True)
    last_run = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'tasks'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['priority']),
            models.Index(fields=['dept']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-priority', '-created_at']

    def __str__(self):
        return f"{self.id} - {self.name}"


class TaskDependency(models.Model):
    DEPENDENCY_TYPE_CHOICES = [
        ('sequential', 'Sequential'),
        ('parallel', 'Parallel'),
        ('conditional', 'Conditional'),
    ]

    id = models.CharField(max_length=50, primary_key=True, default=make_dep_id)
    from_task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='outgoing_dependencies')
    to_task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='incoming_dependencies')
    dependency_type = models.CharField(max_length=20, choices=DEPENDENCY_TYPE_CHOICES, default='sequential')
    label = models.CharField(max_length=255, blank=True, null=True)
    condition = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'task_dependencies'
        unique_together = ['from_task', 'to_task']

    def __str__(self):
        return f"{self.from_task.id} -> {self.to_task.id} ({self.dependency_type})"


class Goal(models.Model):
    STATUS_CHOICES = [
        ('parsing', 'Parsing'),
        ('parsed', 'Parsed'),
        ('building', 'Building Tasks'),
        ('ready', 'Ready'),
        ('executing', 'Executing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    id = models.CharField(max_length=50, primary_key=True, default=make_goal_id)
    user_input = models.TextField()
    parsed_goal = models.CharField(max_length=500, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='parsing')
    llm_response = models.JSONField(default=dict, blank=True)
    structured_tasks = models.JSONField(default=list, blank=True)
    error_message = models.TextField(blank=True, null=True)
    parsing_time_ms = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'goals'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.id} - {self.user_input[:50]}"


class GoalTemplate(models.Model):
    id = models.CharField(max_length=50, primary_key=True, default=make_tmpl_id)
    name = models.CharField(max_length=255)
    goal_text = models.TextField()
    template_tasks = models.JSONField(default=list)
    category = models.CharField(max_length=100, blank=True, null=True)
    usage_count = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'goal_templates'
        ordering = ['-usage_count', 'name']

    def __str__(self):
        return self.name


class TaskExecutionHistory(models.Model):
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('timeout', 'Timeout'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.CharField(max_length=50, primary_key=True, default=make_hist_id)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='execution_history')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.IntegerField(null=True, blank=True)
    agent = models.CharField(max_length=100, blank=True, null=True)
    dept = models.CharField(max_length=50, choices=Task.DEPT_CHOICES)
    error_details = models.JSONField(default=dict, blank=True)
    retry_count = models.IntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'task_execution_history'
        indexes = [
            models.Index(fields=['task', 'started_at']),
            models.Index(fields=['status']),
        ]
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.task.id} - {self.status} - {self.started_at}"


class BottleneckAlert(models.Model):
    SEVERITY_CHOICES = [
        ('critical', 'Critical'),
        ('high', 'High'),
        ('warning', 'Warning'),
        ('info', 'Info'),
    ]

    id = models.CharField(max_length=50, primary_key=True, default=make_alert_id)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, null=True, blank=True)
    task_name = models.CharField(max_length=255)
    issue = models.TextField()
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    impact = models.TextField()
    detected_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_note = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'bottleneck_alerts'
        ordering = ['-detected_at']

    def __str__(self):
        return f"{self.task_name} - {self.severity}"


class MonthlyPerformance(models.Model):
    id = models.CharField(max_length=50, primary_key=True, default=make_perf_id)
    month = models.CharField(max_length=3)
    year = models.IntegerField()
    tasks_completed = models.IntegerField(default=0)
    tasks_failed = models.IntegerField(default=0)
    avg_execution_ms = models.IntegerField(default=0)
    on_time_percentage = models.FloatField(default=0.0)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'monthly_performance'
        unique_together = ['month', 'year']
        ordering = ['year', 'month']

    def __str__(self):
        return f"{self.month} {self.year} - {self.tasks_completed} tasks"
from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Task, TaskDependency, Goal, GoalTemplate,
    TaskExecutionHistory, BottleneckAlert, MonthlyPerformance
)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'status_badge', 'priority_badge', 'dept', 'progress_bar', 'created_at']
    list_filter = ['status', 'priority', 'dept', 'exec_mode']
    search_fields = ['name', 'description', 'id']
    readonly_fields = ['id', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'name', 'description', 'status', 'priority', 'dept')
        }),
        ('Execution', {
            'fields': ('assignee', 'depends_on', 'schedule', 'deadline', 'exec_mode', 'parallel_execution')
        }),
        ('Progress', {
            'fields': ('progress', 'estimated_steps', 'actual_duration_ms', 'last_run')
        }),
        ('Metadata', {
            'fields': ('conditions', 'metadata', 'created_by', 'created_at', 'updated_at')
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'running': 'blue',
            'completed': 'green',
            'pending': 'yellow',
            'blocked': 'red',
            'scheduled': 'purple',
            'idle': 'gray',
            'failed': 'red'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 8px; border-radius: 4px;">{}</span>',
            color, obj.status
        )
    status_badge.short_description = 'Status'
    
    def priority_badge(self, obj):
        colors = {
            'critical': 'red',
            'high': 'orange',
            'normal': 'blue',
            'low': 'gray'
        }
        color = colors.get(obj.priority, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 8px; border-radius: 4px;">{}</span>',
            color, obj.priority
        )
    priority_badge.short_description = 'Priority'
    
    def progress_bar(self, obj):
        return format_html(
            '<div style="width: 100px; background: #eee; border-radius: 4px;">'
            '<div style="width: {}%; background: #3a9aab; height: 20px; border-radius: 4px; text-align: center; color: white;">{}%</div>'
            '</div>',
            obj.progress, obj.progress
        )
    progress_bar.short_description = 'Progress'


@admin.register(TaskDependency)
class TaskDependencyAdmin(admin.ModelAdmin):
    list_display = ['id', 'from_task', 'to_task', 'dependency_type', 'created_at']
    list_filter = ['dependency_type']
    search_fields = ['from_task__name', 'to_task__name']
    autocomplete_fields = ['from_task', 'to_task']


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ['id', 'user_input_preview', 'status_badge', 'parsing_time_ms', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['user_input', 'parsed_goal', 'id']
    readonly_fields = ['id', 'created_at', 'updated_at', 'parsing_time_ms']
    
    def user_input_preview(self, obj):
        return obj.user_input[:50] + '...' if len(obj.user_input) > 50 else obj.user_input
    user_input_preview.short_description = 'User Input'
    
    def status_badge(self, obj):
        colors = {
            'parsing': 'blue',
            'parsed': 'cyan',
            'building': 'purple',
            'ready': 'green',
            'executing': 'orange',
            'completed': 'green',
            'failed': 'red'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 8px; border-radius: 4px;">{}</span>',
            color, obj.status
        )
    status_badge.short_description = 'Status'


@admin.register(GoalTemplate)
class GoalTemplateAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'category', 'usage_count', 'is_active']
    list_filter = ['is_active', 'category']
    search_fields = ['name', 'goal_text']
    readonly_fields = ['id', 'usage_count', 'created_at', 'updated_at']


@admin.register(BottleneckAlert)
class BottleneckAlertAdmin(admin.ModelAdmin):
    list_display = ['id', 'task_name', 'severity_badge', 'detected_at', 'resolved_at']
    list_filter = ['severity', 'detected_at']
    search_fields = ['task_name', 'issue']
    readonly_fields = ['id', 'detected_at']
    
    def severity_badge(self, obj):
        colors = {
            'critical': 'red',
            'high': 'orange',
            'warning': 'yellow',
            'info': 'blue'
        }
        color = colors.get(obj.severity, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 8px; border-radius: 4px;">{}</span>',
            color, obj.severity
        )
    severity_badge.short_description = 'Severity'


@admin.register(MonthlyPerformance)
class MonthlyPerformanceAdmin(admin.ModelAdmin):
    list_display = ['id', 'month', 'year', 'tasks_completed', 'on_time_percentage_bar', 'avg_execution_ms']
    list_filter = ['year', 'month']
    readonly_fields = ['id']
    
    def on_time_percentage_bar(self, obj):
        color = '#4ade80' if obj.on_time_percentage >= 95 else '#fbbf24' if obj.on_time_percentage >= 92 else '#f87171'
        return format_html(
            '<div style="width: 100px; background: #eee; border-radius: 4px;">'
            '<div style="width: {}%; background: {}; height: 20px; border-radius: 4px; text-align: center; color: white;">{:.1f}%</div>'
            '</div>',
            obj.on_time_percentage, color, obj.on_time_percentage
        )
    on_time_percentage_bar.short_description = 'On-Time %'


@admin.register(TaskExecutionHistory)
class TaskExecutionHistoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'task', 'status_badge', 'started_at', 'duration_ms']
    list_filter = ['status', 'started_at', 'dept']
    search_fields = ['task__name', 'agent']
    readonly_fields = ['id']
    
    def status_badge(self, obj):
        colors = {
            'success': 'green',
            'failed': 'red',
            'timeout': 'orange',
            'cancelled': 'gray'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 8px; border-radius: 4px;">{}</span>',
            color, obj.status
        )
    status_badge.short_description = 'Status'
"""
crmapp/agentic/analytics/admin.py
"""

from django.contrib import admin
from .models import AgentDailyStat, AgentKPI, AgentWeeklyTask, HITLFeedback


@admin.register(AgentDailyStat)
class AgentDailyStatAdmin(admin.ModelAdmin):
    list_display  = ("resource", "date", "tasks_completed", "tasks_failed",
                     "accuracy", "kpi_score", "trend")
    list_filter   = ("date",)
    search_fields = ("resource__name",)
    ordering      = ("-date", "resource__name")
    readonly_fields = ("created_at",)


@admin.register(AgentKPI)
class AgentKPIAdmin(admin.ModelAdmin):
    list_display  = ("label", "resource", "scope", "target", "actual", "unit", "invert", "recorded_at")
    list_filter   = ("scope", "invert")
    search_fields = ("label", "resource__name")
    ordering      = ("scope", "label")


@admin.register(HITLFeedback)
class HITLFeedbackAdmin(admin.ModelAdmin):
    list_display  = ("agent_name", "supervisor_name", "action", "impact", "created_at")
    list_filter   = ("action", "impact")
    search_fields = ("agent_name", "supervisor_name", "reason")
    ordering      = ("-created_at",)
    readonly_fields = ("created_at",)


@admin.register(AgentWeeklyTask)
class AgentWeeklyTaskAdmin(admin.ModelAdmin):
    list_display  = ("resource", "week_end", "updated_at")
    search_fields = ("resource__name",)
    ordering      = ("-week_end",)

"""
crmapp/agentic/analytics/serializers.py

Serializers for the Agent Performance Analytics dashboard.
"""

from rest_framework import serializers
from crmapp.agentic.core.models import Resource
from .models import AgentKPI, AgentDailyStat, HITLFeedback, AgentWeeklyTask


# ── Primitive helpers ──────────────────────────────────────────────────────────

class AgentKPISerializer(serializers.ModelSerializer):
    attainment_pct = serializers.SerializerMethodField()
    on_target      = serializers.SerializerMethodField()

    class Meta:
        model  = AgentKPI
        fields = [
            "id", "resource", "scope", "label", "target", "actual",
            "unit", "invert", "attainment_pct", "on_target", "recorded_at",
        ]

    def get_attainment_pct(self, obj):
        if obj.invert:
            if obj.actual == 0:
                return 100.0
            raw = (obj.target / obj.actual) * 100
        else:
            if obj.target == 0:
                return 100.0
            raw = (obj.actual / obj.target) * 100
        return round(min(raw, 100.0), 1)

    def get_on_target(self, obj):
        if obj.invert:
            return obj.actual <= obj.target
        return obj.actual >= obj.target


class AgentDailyStatSerializer(serializers.ModelSerializer):
    agent_name = serializers.CharField(source="resource.name", read_only=True)
    domain     = serializers.SerializerMethodField()
    color      = serializers.CharField(source="resource.color", read_only=True)

    class Meta:
        model  = AgentDailyStat
        fields = [
            "id", "resource", "agent_name", "domain", "color", "date",
            "tasks_completed", "tasks_pending", "tasks_failed",
            "errors_today", "human_overrides", "sla_breaches",
            "accuracy", "avg_response_ms", "kpi_score",
            "trend", "trend_up", "created_at",
        ]

    def get_domain(self, obj):
        return obj.resource.metadata.get("dept", "General")


class HITLFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model  = HITLFeedback
        fields = [
            "id", "resource", "agent_name", "supervisor",
            "supervisor_name", "action", "reason", "impact",
            "execution_id", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate_action(self, value):
        valid = {c[0] for c in HITLFeedback.ACTION_CHOICES}
        if value not in valid:
            raise serializers.ValidationError(f"action must be one of {valid}")
        return value

    def validate_impact(self, value):
        valid = {c[0] for c in HITLFeedback.IMPACT_CHOICES}
        if value not in valid:
            raise serializers.ValidationError(f"impact must be one of {valid}")
        return value


class AgentWeeklyTaskSerializer(serializers.ModelSerializer):
    agent_name = serializers.CharField(source="resource.name", read_only=True)

    class Meta:
        model  = AgentWeeklyTask
        fields = ["id", "resource", "agent_name", "counts", "week_end", "updated_at"]
        read_only_fields = ["id", "updated_at"]


# ── Compound response shapes ───────────────────────────────────────────────────

class AgentSummarySerializer(serializers.ModelSerializer):
    """
    Flat summary for one agent — the shape that powers each AgentPerfCard
    in the frontend.  All fields come from AgentDailyStat (latest) +
    AgentWeeklyTask + AgentConfig.
    """
    agent_id        = serializers.CharField(source="id")
    name            = serializers.CharField()
    domain          = serializers.SerializerMethodField()
    color           = serializers.CharField()
    kpi_score       = serializers.SerializerMethodField()
    tasks_completed = serializers.SerializerMethodField()
    tasks_pending   = serializers.SerializerMethodField()
    tasks_failed    = serializers.SerializerMethodField()
    accuracy        = serializers.SerializerMethodField()
    avg_response_ms = serializers.SerializerMethodField()
    errors_today    = serializers.SerializerMethodField()
    human_overrides = serializers.SerializerMethodField()
    sla_breaches    = serializers.SerializerMethodField()
    trend           = serializers.SerializerMethodField()
    trend_up        = serializers.SerializerMethodField()
    weekly_tasks    = serializers.SerializerMethodField()

    class Meta:
        model  = Resource
        fields = [
            "agent_id", "name", "domain", "color",
            "kpi_score",
            "tasks_completed", "tasks_pending", "tasks_failed",
            "accuracy", "avg_response_ms",
            "errors_today", "human_overrides", "sla_breaches",
            "trend", "trend_up",
            "weekly_tasks",
        ]

    # ── helpers ────────────────────────────────────────────────────────────────

    def _latest_stat(self, obj):
        """Return the most recent AgentDailyStat for this resource (cached)."""
        cache = self.context.get("_stat_cache")
        if cache is None:
            return obj.daily_stats.first()
        return cache.get(obj.id)

    def get_domain(self, obj):
        return obj.metadata.get("dept", "General")

    def get_kpi_score(self, obj):
        stat = self._latest_stat(obj)
        return stat.kpi_score if stat else 0

    def get_tasks_completed(self, obj):
        stat = self._latest_stat(obj)
        return stat.tasks_completed if stat else 0

    def get_tasks_pending(self, obj):
        stat = self._latest_stat(obj)
        return stat.tasks_pending if stat else 0

    def get_tasks_failed(self, obj):
        stat = self._latest_stat(obj)
        return stat.tasks_failed if stat else 0

    def get_accuracy(self, obj):
        stat = self._latest_stat(obj)
        return stat.accuracy if stat else 0.0

    def get_avg_response_ms(self, obj):
        stat = self._latest_stat(obj)
        return stat.avg_response_ms if stat else 0

    def get_errors_today(self, obj):
        stat = self._latest_stat(obj)
        return stat.errors_today if stat else 0

    def get_human_overrides(self, obj):
        stat = self._latest_stat(obj)
        return stat.human_overrides if stat else 0

    def get_sla_breaches(self, obj):
        stat = self._latest_stat(obj)
        return stat.sla_breaches if stat else 0

    def get_trend(self, obj):
        stat = self._latest_stat(obj)
        return stat.trend if stat else "+0.0%"

    def get_trend_up(self, obj):
        stat = self._latest_stat(obj)
        return stat.trend_up if stat else True

    def get_weekly_tasks(self, obj):
        try:
            return obj.weekly_tasks.counts
        except AgentWeeklyTask.DoesNotExist:
            return [0] * 7


class FleetOverviewSerializer(serializers.Serializer):
    """
    Top-level response for GET /api/agentic/analytics/overview/
    Matches the STATS + KPIS constants in the frontend.
    """
    total_tasks_today  = serializers.IntegerField()
    avg_accuracy       = serializers.FloatField()
    human_overrides    = serializers.IntegerField()
    agents_below_kpi   = serializers.IntegerField()
    agents             = AgentSummarySerializer(many=True)
    fleet_kpis         = AgentKPISerializer(many=True)

"""
crmapp/agentic/analytics/models.py

Persists analytics data that the Agent Performance Analytics dashboard
reads from:
  - AgentKPI          — per-agent KPI target + actual snapshots
  - AgentDailyStat    — daily rollup of completed/failed/pending/errors per agent
  - HITLFeedback      — human-in-the-loop override/correction records
  - AgentWeeklyTask   — 7-day task count history per agent (for the mini bar chart)

All models reference crmapp.agentic.core.models.Resource (the agent).
"""

import uuid
from django.db import models
from django.contrib.auth.models import User
from crmapp.agentic.core.models import Resource


def make_kpi_id():
    return f"kpi-{uuid.uuid4().hex[:6]}"

def make_stat_id():
    return f"stat-{uuid.uuid4().hex[:6]}"

def make_hitl_id():
    return f"hitl-{uuid.uuid4().hex[:6]}"

def make_weekly_id():
    return f"wkly-{uuid.uuid4().hex[:6]}"


# ── 1. Per-agent KPI targets & actuals ────────────────────────────────────────

class AgentKPI(models.Model):
    """
    Stores the target and most-recent actual value for a named KPI,
    scoped to either a specific agent (resource) or the whole fleet (resource=NULL).
    """
    SCOPE_CHOICES = [
        ("agent",  "Per Agent"),
        ("global", "Fleet-Wide"),
    ]

    id         = models.CharField(max_length=50, primary_key=True, default=make_kpi_id)
    resource   = models.ForeignKey(
        Resource,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="kpis",
        help_text="NULL = fleet-wide KPI",
    )
    scope      = models.CharField(max_length=10, choices=SCOPE_CHOICES, default="agent")
    label      = models.CharField(max_length=200)          # e.g. "Avg Accuracy"
    target     = models.FloatField()                       # numeric target
    actual     = models.FloatField()                       # latest actual value
    unit       = models.CharField(max_length=20, blank=True, default="")  # "%", "ms", ""
    invert     = models.BooleanField(
        default=False,
        help_text="True when lower is better (e.g. response time)",
    )
    recorded_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "agent_kpis"
        ordering = ["label"]
        unique_together = [["resource", "label"]]

    def __str__(self):
        agent = self.resource.name if self.resource else "Fleet"
        return f"{agent} — {self.label}: {self.actual}/{self.target}"


# ── 2. Daily rollup stats per agent ───────────────────────────────────────────

class AgentDailyStat(models.Model):
    """
    One row per agent per calendar date.
    Populated nightly by a management command or Celery beat task.
    The analytics dashboard reads these to power the Overview cards,
    Comparative Analytics, and KPI Tracker.
    """
    id               = models.CharField(max_length=50, primary_key=True, default=make_stat_id)
    resource         = models.ForeignKey(
        Resource,
        on_delete=models.CASCADE,
        related_name="daily_stats",
    )
    date             = models.DateField()

    # Task counts (mirrors the frontend AGENTS data shape)
    tasks_completed  = models.IntegerField(default=0)
    tasks_pending    = models.IntegerField(default=0)
    tasks_failed     = models.IntegerField(default=0)
    errors_today     = models.IntegerField(default=0)
    human_overrides  = models.IntegerField(default=0)
    sla_breaches     = models.IntegerField(default=0)

    # Performance metrics
    accuracy         = models.FloatField(default=0.0)       # 0–100
    avg_response_ms  = models.IntegerField(default=0)
    kpi_score        = models.IntegerField(default=0)       # 0–100 composite

    # Trend vs previous day  e.g. "+4.1%" or "-3.2%"
    trend            = models.CharField(max_length=20, blank=True, default="")
    trend_up         = models.BooleanField(default=True)

    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table      = "agent_daily_stats"
        unique_together = [["resource", "date"]]
        ordering      = ["-date"]

    def __str__(self):
        return f"{self.resource.name} — {self.date}"


# ── 3. Human-in-the-Loop feedback ─────────────────────────────────────────────

class HITLFeedback(models.Model):
    """
    Records every human override, approval, or correction of an agent decision.
    Drives the "Human Feedback" tab in the analytics dashboard.
    """
    ACTION_CHOICES = [
        ("Override",   "Override"),
        ("Approved",   "Approved"),
        ("Correction", "Correction"),
    ]
    IMPACT_CHOICES = [
        ("positive", "Positive"),
        ("neutral",  "Neutral"),
        ("negative", "Negative"),
    ]

    id           = models.CharField(max_length=50, primary_key=True, default=make_hitl_id)
    resource     = models.ForeignKey(
        Resource,
        on_delete=models.SET_NULL,
        null=True,
        related_name="hitl_feedback",
    )
    # Denormalised agent name — survives agent deletion
    agent_name   = models.CharField(max_length=200)

    supervisor   = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hitl_actions",
    )
    supervisor_name = models.CharField(max_length=200, blank=True, default="")

    action       = models.CharField(max_length=20, choices=ACTION_CHOICES)
    reason       = models.TextField()
    impact       = models.CharField(max_length=20, choices=IMPACT_CHOICES, default="neutral")

    # Optional link to the execution that was overridden
    execution_id = models.CharField(max_length=50, blank=True, default="")

    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hitl_feedback"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.supervisor_name} → {self.agent_name}: {self.action}"


# ── 4. Per-agent 7-day task counts (for the mini bar chart) ───────────────────

class AgentWeeklyTask(models.Model):
    """
    Stores the 7 most-recent daily task-completed counts per agent.
    The analytics frontend renders these as the mini bar chart on each agent card.

    The list is ordered Mon→Sun; index 6 is the current day (always highlighted).
    """
    id       = models.CharField(max_length=50, primary_key=True, default=make_weekly_id)
    resource = models.OneToOneField(
        Resource,
        on_delete=models.CASCADE,
        related_name="weekly_tasks",
    )
    # 7 values stored as a JSON array, e.g. [310, 298, 342, 381, 290, 378, 394]
    counts   = models.JSONField(default=list)
    week_end = models.DateField(help_text="The Sunday (last day) of this 7-day window")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "agent_weekly_tasks"

    def __str__(self):
        return f"{self.resource.name} — week ending {self.week_end}"

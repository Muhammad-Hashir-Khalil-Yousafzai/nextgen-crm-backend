"""
crmapp/agentic/analytics/management/commands/seed_analytics.py

Seeds realistic AgentDailyStat, AgentWeeklyTask, HITLFeedback, and
AgentKPI rows to match the hardcoded AGENTS / KPIS / HITL_FEEDBACK
data in the frontend AgentPerformanceAnalytics component.

Run with:
    python manage.py seed_analytics
    python manage.py seed_analytics --days 14   # seed last N days
    python manage.py seed_analytics --clear     # wipe & re-seed
"""

import random
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone


# ── Frontend AGENTS constant replicated here ──────────────────────────────────
AGENT_SEEDS = [
    {
        "name":            "Sales Intelligence Agent",
        "domain":          "Sales",
        "tasks_completed": 2847,
        "tasks_pending":   43,
        "tasks_failed":    12,
        "accuracy":        94.2,
        "sla_breaches":    3,
        "avg_response_ms": 84,
        "errors_today":    12,
        "human_overrides": 8,
        "kpi_score":       91,
        "trend":           "+4.1%",
        "trend_up":        True,
        "weekly_tasks":    [310, 298, 342, 381, 290, 378, 394],
        "errors": [
            {"type": "Timeout",       "count": 5},
            {"type": "Data missing",  "count": 4},
            {"type": "Rule conflict", "count": 3},
        ],
    },
    {
        "name":            "Customer Support Agent",
        "domain":          "Support",
        "tasks_completed": 1593,
        "tasks_pending":   21,
        "tasks_failed":    6,
        "accuracy":        97.8,
        "sla_breaches":    4,
        "avg_response_ms": 112,
        "errors_today":    6,
        "human_overrides": 14,
        "kpi_score":       96,
        "trend":           "+2.3%",
        "trend_up":        True,
        "weekly_tasks":    [201, 218, 234, 241, 228, 247, 253],
        "errors": [
            {"type": "SLA breach", "count": 4},
            {"type": "Timeout",    "count": 2},
        ],
    },
    {
        "name":            "Finance Recovery Agent",
        "domain":          "Finance",
        "tasks_completed": 8421,
        "tasks_pending":   14,
        "tasks_failed":    3,
        "accuracy":        99.1,
        "sla_breaches":    0,
        "avg_response_ms": 19,
        "errors_today":    3,
        "human_overrides": 2,
        "kpi_score":       99,
        "trend":           "+0.8%",
        "trend_up":        True,
        "weekly_tasks":    [1102, 1240, 1189, 1321, 1284, 1301, 1414],
        "errors": [
            {"type": "API timeout", "count": 2},
            {"type": "Model miss",  "count": 1},
        ],
    },
    {
        "name":            "Marketing Automation Agent",
        "domain":          "Mktg",
        "tasks_completed": 1028,
        "tasks_pending":   18,
        "tasks_failed":    22,
        "accuracy":        88.6,
        "sla_breaches":    7,
        "avg_response_ms": 204,
        "errors_today":    22,
        "human_overrides": 19,
        "kpi_score":       82,
        "trend":           "+1.1%",
        "trend_up":        True,
        "weekly_tasks":    [138, 141, 152, 148, 162, 154, 171],
        "errors": [
            {"type": "Budget limit", "count": 11},
            {"type": "API error",    "count": 7},
            {"type": "Timeout",      "count": 4},
        ],
    },
    {
        "name":            "CRM Analytics Agent",
        "domain":          "HR",
        "tasks_completed": 384,
        "tasks_pending":   48,
        "tasks_failed":    31,
        "accuracy":        91.4,
        "sla_breaches":    9,
        "avg_response_ms": 340,
        "errors_today":    31,
        "human_overrides": 22,
        "kpi_score":       74,
        "trend":           "-3.2%",
        "trend_up":        False,
        "weekly_tasks":    [72, 68, 61, 74, 48, 31, 30],
        "errors": [
            {"type": "Agent paused", "count": 18},
            {"type": "Data error",   "count": 8},
            {"type": "Timeout",      "count": 5},
        ],
    },
    {
        "name":            "Invoice Collector Agent",
        "domain":          "Ops",
        "tasks_completed": 241,
        "tasks_pending":   9,
        "tasks_failed":    47,
        "accuracy":        70.6,
        "sla_breaches":    18,
        "avg_response_ms": 891,
        "errors_today":    47,
        "human_overrides": 31,
        "kpi_score":       58,
        "trend":           "-8.4%",
        "trend_up":        False,
        "weekly_tasks":    [54, 48, 41, 38, 29, 21, 10],
        "errors": [
            {"type": "ERP timeout", "count": 31},
            {"type": "Data stale",  "count": 11},
            {"type": "Rule fail",   "count": 5},
        ],
    },
]


# ── Frontend HITL_FEEDBACK replicated ─────────────────────────────────────────
HITL_SEEDS = [
    {
        "agent":      "Customer Support Agent",
        "supervisor": "Sara Ahmed",
        "action":     "Override",
        "reason":     "Agent escalated unnecessarily — resolved manually",
        "impact":     "positive",
        "hours_ago":  2,
    },
    {
        "agent":      "Sales Intelligence Agent",
        "supervisor": "Ali Khan",
        "action":     "Approved",
        "reason":     "Decision aligned with territory strategy",
        "impact":     "neutral",
        "hours_ago":  4,
    },
    {
        "agent":      "CRM Analytics Agent",
        "supervisor": "Nour Malik",
        "action":     "Correction",
        "reason":     "Candidate shortlisted incorrectly — skills mismatch",
        "impact":     "negative",
        "hours_ago":  5,
    },
    {
        "agent":      "Marketing Automation Agent",
        "supervisor": "Zara Siddiq",
        "action":     "Override",
        "reason":     "Budget cap too conservative for Q1 target",
        "impact":     "positive",
        "hours_ago":  8,
    },
    {
        "agent":      "Sales Prioritization",
        "supervisor": "Omar Baig",
        "action":     "Correction",
        "reason":     "ERP data was stale — manual restock triggered",
        "impact":     "negative",
        "hours_ago":  11,
    },
]


# ── Fleet KPI targets ──────────────────────────────────────────────────────────
FLEET_KPI_SEEDS = [
    {"label": "Tasks Completed/Day", "target": 1500, "actual": 2422, "unit": "",    "invert": False},
    {"label": "Avg Accuracy",        "target": 95,   "actual": 90.3, "unit": "%",   "invert": False},
    {"label": "Avg Response Time",   "target": 200,  "actual": 275,  "unit": "ms",  "invert": True},
    {"label": "SLA Adherence",       "target": 98,   "actual": 96.1, "unit": "%",   "invert": False},
]


class Command(BaseCommand):
    help = "Seeds AgentDailyStat, AgentWeeklyTask, HITLFeedback, and AgentKPI tables"

    def add_arguments(self, parser):
        parser.add_argument("--days",  type=int, default=7,    help="How many past days to seed stats for")
        parser.add_argument("--clear", action="store_true",    help="Delete all analytics data before seeding")

    def handle(self, *args, **options):
        from crmapp.agentic.core.models import Resource
        from crmapp.agentic.analytics.models import (
            AgentDailyStat, AgentWeeklyTask, HITLFeedback, AgentKPI
        )

        if options["clear"]:
            AgentDailyStat.objects.all().delete()
            AgentWeeklyTask.objects.all().delete()
            HITLFeedback.objects.all().delete()
            AgentKPI.objects.filter(scope="global").delete()
            self.stdout.write(self.style.WARNING("Cleared all analytics data."))

        today      = date.today()
        days       = options["days"]
        stat_count = 0
        skip_count = 0

        # ── 1. AgentDailyStat + AgentWeeklyTask ────────────────────────────
        self.stdout.write(f"\nSeeding daily stats for last {days} days...")

        
        for seed in AGENT_SEEDS:
            resource = Resource.objects.filter(name=seed["name"]).first()
            if not resource:
                resource = Resource.objects.filter(
                    name__istartswith=seed["name"].split("(")[0].strip(),
                    type="AI Agent"
                ).first()
            if not resource:
                self.stdout.write(self.style.WARNING(
                    f"  Skipping '{seed['name']}' — resource not found (run seed_agents first)"
                ))
                skip_count += 1
                continue  # ← same level as skip_count += 1

            for day_offset in range(days - 1, -1, -1):
                stat_date = today - timedelta(days=day_offset)

                # Add realistic daily variance (±10%)
                noise = lambda v, spread=0.10: max(0, int(v * (1 + random.uniform(-spread, spread))))

                _, created = AgentDailyStat.objects.update_or_create(
                    resource=resource,
                    date=stat_date,
                    defaults={
                        "tasks_completed":  noise(seed["tasks_completed"]),
                        "tasks_pending":    noise(seed["tasks_pending"], 0.30),
                        "tasks_failed":     noise(seed["tasks_failed"]),
                        "errors_today":     noise(seed["errors_today"]),
                        "human_overrides":  noise(seed["human_overrides"], 0.20),
                        "sla_breaches":     noise(seed["sla_breaches"], 0.20),
                        "accuracy":         round(seed["accuracy"] + random.uniform(-1.5, 1.5), 1),
                        "avg_response_ms":  noise(seed["avg_response_ms"], 0.15),
                        "kpi_score":        min(100, max(0, seed["kpi_score"] + random.randint(-3, 3))),
                        "trend":            seed["trend"],
                        "trend_up":         seed["trend_up"],
                    },
                )
                stat_count += 1

            # Weekly task counts (use exact seed data for the current week)
            AgentWeeklyTask.objects.update_or_create(
                resource=resource,
                defaults={
                    "counts":   seed["weekly_tasks"],
                    "week_end": today,
                },
            )
            self.stdout.write(f"  ✓ {resource.name} [{seed['domain']}]")

        # ── 2. HITLFeedback ────────────────────────────────────────────────
        self.stdout.write("\nSeeding HITL feedback...")
        for hf in HITL_SEEDS:
            resource = Resource.objects.filter(name=hf["agent"]).first()
            created_at = timezone.now() - timedelta(hours=hf["hours_ago"])

            fb = HITLFeedback(
                resource=resource,
                agent_name=hf["agent"],
                supervisor_name=hf["supervisor"],
                action=hf["action"],
                reason=hf["reason"],
                impact=hf["impact"],
            )
            # Override auto_now_add by saving with update_fields trick
            fb.save()
            # Force the created_at timestamp
            HITLFeedback.objects.filter(pk=fb.pk).update(created_at=created_at)
            self.stdout.write(f"  ✓ {hf['supervisor']} → {hf['agent']}: {hf['action']}")

        # ── 3. Fleet-wide AgentKPI ─────────────────────────────────────────
        self.stdout.write("\nSeeding fleet KPIs...")
        for kpi in FLEET_KPI_SEEDS:
            AgentKPI.objects.update_or_create(
                resource=None,
                label=kpi["label"],
                defaults={
                    "scope":  "global",
                    "target": kpi["target"],
                    "actual": kpi["actual"],
                    "unit":   kpi["unit"],
                    "invert": kpi["invert"],
                },
            )
            self.stdout.write(f"  ✓ {kpi['label']}: {kpi['actual']} / {kpi['target']}{kpi['unit']}")

        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Done!\n"
            f"   {stat_count} daily-stat rows seeded  |  {skip_count} agents skipped\n"
            f"   {len(HITL_SEEDS)} HITL feedback rows  |  {len(FLEET_KPI_SEEDS)} fleet KPIs\n"
            f"   Test at: http://localhost:8000/api/agentic/analytics/overview/"
        ))


# Required import used inside handle()
from crmapp.agentic.analytics.models import HITLFeedback  # noqa: E402

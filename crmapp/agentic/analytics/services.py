"""
crmapp/agentic/analytics/services.py

AnalyticsSyncService — computes AgentDailyStat and AgentWeeklyTask rows
from raw AgentExecution data.

Called by:
  - POST /api/agentic/analytics/stats/sync/   (manual / backfill)
  - Celery beat task  (nightly at 00:05)
"""

import logging
from datetime import date, timedelta
from django.db.models import Avg, Count, Q
from django.utils import timezone

from crmapp.agentic.core.models import Resource
from crmapp.agentic.agents.models import AgentExecution
from .models import AgentDailyStat, AgentKPI, AgentWeeklyTask

logger = logging.getLogger(__name__)


class AnalyticsSyncService:

    # ── Public entry point ────────────────────────────────────────────────────

    def sync_date(self, sync_date: date) -> dict:
        """
        Recompute AgentDailyStat for every AI-Agent Resource for sync_date.
        Also refreshes AgentWeeklyTask (7-day window ending sync_date).
        Returns a summary report dict.
        """
        resources = Resource.objects.filter(type__iexact="AI Agent")
        created = updated = 0

        for resource in resources:
            stat, was_created = self._compute_stat(resource, sync_date)
            if was_created:
                created += 1
            else:
                updated += 1
            self._refresh_weekly(resource, sync_date)

        self._refresh_fleet_kpis(sync_date)

        return {
            "agents_processed": resources.count(),
            "stats_created":    created,
            "stats_updated":    updated,
            "date":             str(sync_date),
        }

    # ── Per-agent daily stat ──────────────────────────────────────────────────

    def _compute_stat(self, resource: Resource, for_date: date):
        """
        Build one AgentDailyStat row from AgentExecution rows for the day.
        KPI score is a simple composite:
            0.40 * accuracy_norm
          + 0.25 * (1 - error_rate)
          + 0.20 * sla_ok_norm
          + 0.15 * response_speed_norm
        """
        executions = AgentExecution.objects.filter(
            resource=resource,
            started_at__date=for_date,
        )

        total     = executions.count()
        completed = executions.filter(status="success").count()
        failed    = executions.filter(status="failed").count()
        pending   = executions.filter(status__in=["pending", "running"]).count()

        # Accuracy: success / total (avoid div/0)
        accuracy = round((completed / total * 100), 1) if total > 0 else 0.0

        # Avg response time (ms) — only for finished executions
        avg_rt_data = executions.filter(
            duration_ms__isnull=False
        ).aggregate(avg=Avg("duration_ms"))
        avg_response_ms = int(avg_rt_data["avg"] or 0)

        # Errors = failed executions today
        errors_today = failed

        # Human overrides — count HITL records for this agent today
        try:
            from .models import HITLFeedback
            human_overrides = HITLFeedback.objects.filter(
                resource=resource,
                created_at__date=for_date,
            ).count()
        except Exception:
            human_overrides = 0

        # SLA breaches — stored in raw_output["sla_breach"]=true on each execution
        sla_breaches = executions.filter(
            raw_output__sla_breach=True
        ).count()

        # KPI score composite (0–100)
        accuracy_norm      = accuracy / 100
        error_rate         = (failed / total) if total > 0 else 0
        sla_ok             = 1 - (sla_breaches / max(total, 1))
        # response speed: target = 200 ms; score = min(target/actual, 1)
        resp_target        = 200
        resp_norm          = min(resp_target / avg_response_ms, 1.0) if avg_response_ms > 0 else 1.0

        kpi_score = int(round(
            0.40 * accuracy_norm * 100
          + 0.25 * (1 - error_rate) * 100
          + 0.20 * sla_ok * 100
          + 0.15 * resp_norm * 100
        ))

        # Trend: compare kpi_score to yesterday
        yesterday_stat = AgentDailyStat.objects.filter(
            resource=resource,
            date=for_date - timedelta(days=1),
        ).first()

        if yesterday_stat and yesterday_stat.kpi_score > 0:
            delta = kpi_score - yesterday_stat.kpi_score
            trend    = f"{'+' if delta >= 0 else ''}{delta / yesterday_stat.kpi_score * 100:.1f}%"
            trend_up = delta >= 0
        else:
            trend    = "+0.0%"
            trend_up = True

        stat, created = AgentDailyStat.objects.update_or_create(
            resource=resource,
            date=for_date,
            defaults={
                "tasks_completed":  completed,
                "tasks_pending":    pending,
                "tasks_failed":     failed,
                "errors_today":     errors_today,
                "human_overrides":  human_overrides,
                "sla_breaches":     sla_breaches,
                "accuracy":         accuracy,
                "avg_response_ms":  avg_response_ms,
                "kpi_score":        kpi_score,
                "trend":            trend,
                "trend_up":         trend_up,
            },
        )
        return stat, created

    # ── Weekly task counts ────────────────────────────────────────────────────

    def _refresh_weekly(self, resource: Resource, week_end: date):
        """
        Build a 7-element list of tasks_completed counts for
        the 7 days ending on week_end (Mon→Sun window).
        """
        counts = []
        for offset in range(6, -1, -1):   # 6 days ago … today
            day = week_end - timedelta(days=offset)
            stat = AgentDailyStat.objects.filter(
                resource=resource, date=day
            ).first()
            counts.append(stat.tasks_completed if stat else 0)

        AgentWeeklyTask.objects.update_or_create(
            resource=resource,
            defaults={"counts": counts, "week_end": week_end},
        )

    # ── Fleet-wide KPIs ───────────────────────────────────────────────────────

    def _refresh_fleet_kpis(self, for_date: date):
        """
        Upserts the four fleet-wide KPI rows that match the
        frontend's KPIS constant:
          - Tasks Completed/Day   target=1500
          - Avg Accuracy          target=95 %
          - Avg Response Time     target=200 ms  (invert=True)
          - SLA Adherence         target=98 %
        """
        stats = AgentDailyStat.objects.filter(date=for_date)
        if not stats.exists():
            return

        total_completed = sum(s.tasks_completed for s in stats)
        avg_accuracy    = round(
            sum(s.accuracy for s in stats) / stats.count(), 1
        ) if stats.count() > 0 else 0.0
        avg_rt          = int(
            sum(s.avg_response_ms for s in stats) / stats.count()
        ) if stats.count() > 0 else 0
        total_tasks     = sum(s.tasks_completed + s.tasks_failed for s in stats)
        total_breaches  = sum(s.sla_breaches for s in stats)
        sla_adherence   = round(
            (1 - total_breaches / max(total_tasks, 1)) * 100, 1
        )

        fleet_kpis = [
            {
                "label":  "Tasks Completed/Day",
                "target": 1500,
                "actual": total_completed,
                "unit":   "",
                "invert": False,
            },
            {
                "label":  "Avg Accuracy",
                "target": 95,
                "actual": avg_accuracy,
                "unit":   "%",
                "invert": False,
            },
            {
                "label":  "Avg Response Time",
                "target": 200,
                "actual": avg_rt,
                "unit":   "ms",
                "invert": True,
            },
            {
                "label":  "SLA Adherence",
                "target": 98,
                "actual": sla_adherence,
                "unit":   "%",
                "invert": False,
            },
        ]

        for kpi_data in fleet_kpis:
            AgentKPI.objects.update_or_create(
                resource=None,
                label=kpi_data["label"],
                defaults={
                    "scope":  "global",
                    "target": kpi_data["target"],
                    "actual": kpi_data["actual"],
                    "unit":   kpi_data["unit"],
                    "invert": kpi_data["invert"],
                },
            )

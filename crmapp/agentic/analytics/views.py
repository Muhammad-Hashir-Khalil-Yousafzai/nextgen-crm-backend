"""
crmapp/agentic/analytics/views.py  — fixed CompareViewSet + overview fallback
"""

import logging
from datetime import date, timedelta

from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from crmapp.agentic.core.models import Resource
from crmapp.agentic.agents.models import AgentExecution

from .models import AgentDailyStat, AgentKPI, AgentWeeklyTask, HITLFeedback
from .serializers import (
    AgentDailyStatSerializer,
    AgentKPISerializer,
    AgentSummarySerializer,
    AgentWeeklyTaskSerializer,
    HITLFeedbackSerializer,
)
from .services import AnalyticsSyncService

logger = logging.getLogger(__name__)


# ── helper: get the best available stats queryset ─────────────────────────────
def _best_stats(resource_qs=None):
    """
    Return the most recent AgentDailyStat rows.
    Priority: today → yesterday → most-recent date in DB → empty.
    Optionally filter to a specific resource queryset.
    """
    qs = AgentDailyStat.objects.select_related("resource")
    if resource_qs is not None:
        qs = qs.filter(resource__in=resource_qs)

    for days_back in [0, 1]:
        candidate = qs.filter(date=date.today() - timedelta(days=days_back))
        if candidate.exists():
            return candidate

    # Fall back to whatever the latest date is (dev / demo scenario)
    latest = qs.order_by("-date").values_list("date", flat=True).first()
    if latest:
        return qs.filter(date=latest)

    return qs.none()


def _best_stat_cache(resource_qs):
    """Return {resource_id: AgentDailyStat} for the best available date."""
    return {s.resource_id: s for s in _best_stats(resource_qs)}


# ─────────────────────────────────────────────────────────────────────────────
# 1.  Overview
# ─────────────────────────────────────────────────────────────────────────────
class OverviewViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    def list(self, request):
        resources     = Resource.objects.filter(type__iexact="AI Agent")
        latest_stats  = _best_stat_cache(resources)

        serializer_context = {"_stat_cache": latest_stats}
        agent_serializer   = AgentSummarySerializer(
            resources, many=True, context=serializer_context
        )
        agent_data = agent_serializer.data

        fleet_kpis     = AgentKPI.objects.filter(scope="global")
        kpi_serializer = AgentKPISerializer(fleet_kpis, many=True)

        total_tasks     = sum(a["tasks_completed"] for a in agent_data)
        avg_accuracy    = (
            round(sum(a["accuracy"] for a in agent_data) / len(agent_data), 1)
            if agent_data else 0.0
        )
        total_overrides = sum(a["human_overrides"] for a in agent_data)
        below_kpi       = sum(1 for a in agent_data if a["kpi_score"] < 80)

        return Response({
            "total_tasks_today": total_tasks,
            "avg_accuracy":      avg_accuracy,
            "human_overrides":   total_overrides,
            "agents_below_kpi":  below_kpi,
            "agents":            agent_data,
            "fleet_kpis":        kpi_serializer.data,
        })


# ─────────────────────────────────────────────────────────────────────────────
# 2.  Agents
# ─────────────────────────────────────────────────────────────────────────────
class AgentAnalyticsViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    def _get_resource(self, pk):
        try:
            return Resource.objects.get(pk=pk, type__iexact="AI Agent")
        except Resource.DoesNotExist:
            return None

    def list(self, request):
        domain = request.query_params.get("domain")
        qs     = Resource.objects.filter(type__iexact="AI Agent")
        if domain and domain != "All":
            qs = qs.filter(metadata__dept=domain)

        stat_cache = _best_stat_cache(qs)
        serializer = AgentSummarySerializer(
            qs, many=True, context={"_stat_cache": stat_cache}
        )
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        resource = self._get_resource(pk)
        if not resource:
            return Response({"error": "Agent not found."}, status=status.HTTP_404_NOT_FOUND)

        stat    = _best_stats(Resource.objects.filter(pk=resource.pk)).first()
        history = AgentDailyStat.objects.filter(resource=resource).order_by("-date")[:30]
        kpis    = AgentKPI.objects.filter(resource=resource)

        data = AgentSummarySerializer(
            resource,
            context={"_stat_cache": {resource.id: stat} if stat else {}}
        ).data
        data["history"] = AgentDailyStatSerializer(history, many=True).data
        data["kpis"]    = AgentKPISerializer(kpis, many=True).data
        return Response(data)

    @action(detail=True, methods=["get"], url_path="errors")
    def errors(self, request, pk=None):
        resource = self._get_resource(pk)
        if not resource:
            return Response({"error": "Agent not found."}, status=status.HTTP_404_NOT_FOUND)

        today      = date.today()
        executions = AgentExecution.objects.filter(
            resource=resource,
            status="failed",
            started_at__date=today,
        )

        error_counts: dict[str, int] = {}
        for ex in executions:
            raw   = ex.error or "Unknown"
            label = raw[:30].split("\n")[0].strip() or "Unknown"
            error_counts[label] = error_counts.get(label, 0) + 1

        breakdown = [
            {"type": label, "count": cnt}
            for label, cnt in sorted(error_counts.items(), key=lambda x: -x[1])
        ]
        return Response({"agent": resource.name, "errors": breakdown})


# ─────────────────────────────────────────────────────────────────────────────
# 3.  KPIs
# ─────────────────────────────────────────────────────────────────────────────
class KPIViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    # Targets that match the frontend KPIS constant
    FLEET_KPI_TARGETS = [
        {"label": "Tasks Completed/Day", "target": 1500, "unit": "",   "invert": False},
        {"label": "Avg Accuracy",        "target": 95,   "unit": "%",  "invert": False},
        {"label": "Avg Response Time",   "target": 200,  "unit": "ms", "invert": True },
        {"label": "SLA Adherence",       "target": 98,   "unit": "%",  "invert": False},
    ]

    def list(self, request):
        scope    = request.query_params.get("scope", "global")
        agent_id = request.query_params.get("agent")

        qs = AgentKPI.objects.all()
        if agent_id:
            qs = qs.filter(resource_id=agent_id)
        else:
            qs = qs.filter(scope=scope)

        # ── Fallback: if AgentKPI table is empty, compute fleet KPIs live ──
        if scope == "global" and not agent_id and not qs.exists():
            return Response(self._compute_live_fleet_kpis())

        return Response(AgentKPISerializer(qs, many=True).data)

    def _compute_live_fleet_kpis(self):
        """
        Compute the 4 fleet KPI cards directly from AgentDailyStat
        (or AgentExecution if stats also empty).
        Returns a list of dicts shaped like AgentKPISerializer output.
        """
        stats = list(_best_stats())

        if stats:
            total_tasks   = sum(s.tasks_completed for s in stats)
            avg_accuracy  = round(sum(s.accuracy for s in stats) / len(stats), 1)
            avg_rt        = int(sum(s.avg_response_ms for s in stats) / len(stats))
            total_all     = sum(s.tasks_completed + s.tasks_failed for s in stats)
            total_breaches= sum(s.sla_breaches for s in stats)
            sla_adherence = round((1 - total_breaches / max(total_all, 1)) * 100, 1)
        else:
            # Zero fallback — table completely empty
            total_tasks   = 0
            avg_accuracy  = 0.0
            avg_rt        = 0
            sla_adherence = 0.0

        actuals = [total_tasks, avg_accuracy, avg_rt, sla_adherence]

        result = []
        for i, kpi in enumerate(self.FLEET_KPI_TARGETS):
            actual = actuals[i]
            target = kpi["target"]
            if kpi["invert"]:
                pct = round((target / actual * 100), 1) if actual > 0 else 100.0
                on_target = actual <= target
            else:
                pct = round(min(actual / target * 100, 100), 1) if target > 0 else 100.0
                on_target = actual >= target

            result.append({
                "id":            f"live-{i}",
                "resource":      None,
                "scope":         "global",
                "label":         kpi["label"],
                "target":        target,
                "actual":        actual,
                "unit":          kpi["unit"],
                "invert":        kpi["invert"],
                "attainment_pct": pct,
                "on_target":     on_target,
                "recorded_at":   None,
            })
        return result

    @action(detail=False, methods=["get"], url_path="rankings")
    def rankings(self, request):
        """
        Rankings use _best_stats() which already has the 4-level fallback,
        so this always returns data as long as agents are registered.
        """
        stats  = list(_best_stats())

        # If stats still empty, build from live executions or placeholders
        if not stats:
            from crmapp.agentic.analytics.views import CompareViewSet
            cv    = CompareViewSet()
            stats = cv._build_live_stats() or cv._build_placeholder_stats()

        ranked = sorted(stats, key=lambda s: s.kpi_score, reverse=True)

        return Response([
            {
                "rank":            i + 1,
                "agent_id":        s.resource_id,
                "agent_name":      s.resource.name,
                "domain":          s.resource.metadata.get("dept", "General"),
                "color":           s.resource.color or "#296571",
                "kpi_score":       s.kpi_score,
                "accuracy":        s.accuracy,
                "avg_response_ms": s.avg_response_ms,
                "trend":           s.trend,
                "trend_up":        s.trend_up,
            }
            for i, s in enumerate(ranked)
        ])


# ─────────────────────────────────────────────────────────────────────────────
# 4.  Comparative Analytics  ← FIXED
# ─────────────────────────────────────────────────────────────────────────────
class CompareViewSet(viewsets.ViewSet):
    """
    Powers the Comparative Analytics tab.

    Data source priority (never returns empty if ANY stats exist):
      1. AgentDailyStat for today
      2. AgentDailyStat for yesterday
      3. Most recent date available in DB
      4. Live fallback: compute directly from AgentExecution (today)
      5. Synthesize placeholder rows from Resource table (zero values)
         so the UI always has something to render.

    ?metric = accuracy | avg_response_ms | kpi_score | errors_today
    """
    permission_classes = [AllowAny]

    METRIC_CONFIG = {
        "accuracy": {
            "label":  "Accuracy (%)",
            "unit":   "%",
            "invert": False,
        },
        "avg_response_ms": {
            "label":  "Avg Response (ms)",
            "unit":   "ms",
            "invert": True,
        },
        "kpi_score": {
            "label":  "KPI Score",
            "unit":   "",
            "invert": False,
        },
        "errors_today": {
            "label":  "Errors Today",
            "unit":   "",
            "invert": True,
        },
    }

    def list(self, request):
        metric = request.query_params.get("metric", "accuracy")
        if metric not in self.METRIC_CONFIG:
            return Response(
                {"error": f"metric must be one of {list(self.METRIC_CONFIG.keys())}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cfg   = self.METRIC_CONFIG[metric]
        stats = list(_best_stats())

        # ── Fallback 1: compute live from AgentExecution if DB stats empty ──
        if not stats:
            stats = self._build_live_stats()

        # ── Fallback 2: synthesize zero-rows from Resource table ──────────
        if not stats:
            stats = self._build_placeholder_stats()

        if not stats:
            return Response({
                "metric":        metric,
                "metric_label":  cfg["label"],
                "metric_unit":   cfg["unit"],
                "invert":        cfg["invert"],
                "ranked":        [],
                "accuracy_dist": [],
                "error_dist":    [],
                "note":          "No agents registered. Run seed_agents first.",
            })

        # ── Sort ──────────────────────────────────────────────────────────
        def sort_key(s):
            val = getattr(s, metric, 0) or 0
            return val if cfg["invert"] else -val

        sorted_stats = sorted(stats, key=sort_key)
        max_val = max((getattr(s, metric, 0) or 0 for s in stats), default=1) or 1

        ranked = []
        for i, s in enumerate(sorted_stats):
            val     = getattr(s, metric, 0) or 0
            bar_pct = (
                round(((max_val - val) / max_val) * 100, 1)
                if cfg["invert"]
                else round((val / max_val) * 100, 1)
            )
            ranked.append({
                "rank":      i + 1,
                "agent_id":  s.resource_id,
                "name":      s.resource.name,
                "domain":    s.resource.metadata.get("dept", "General"),
                "color":     s.resource.color or "#296571",
                "value":     val,
                "bar_pct":   bar_pct,
                "is_top":    i == 0,
            })

        accuracy_dist = [
            {"agent_id": s.resource_id, "name": s.resource.name, "value": s.accuracy or 0}
            for s in sorted(stats, key=lambda x: -(x.accuracy or 0))
        ]
        error_dist = [
            {"agent_id": s.resource_id, "name": s.resource.name, "value": s.errors_today or 0}
            for s in sorted(stats, key=lambda x: -(x.errors_today or 0))
        ]

        return Response({
            "metric":        metric,
            "metric_label":  cfg["label"],
            "metric_unit":   cfg["unit"],
            "invert":        cfg["invert"],
            "ranked":        ranked,
            "accuracy_dist": accuracy_dist,
            "error_dist":    error_dist,
        })

    # ── Live fallback: build transient stat objects from AgentExecution ───
    def _build_live_stats(self):
        """
        When AgentDailyStat is empty, compute metrics on-the-fly from
        AgentExecution rows for today. Returns a list of SimpleNamespace
        objects that quack like AgentDailyStat instances.
        """
        from types import SimpleNamespace

        today     = date.today()
        resources = Resource.objects.filter(type__iexact="AI Agent")
        results   = []

        for resource in resources:
            execs    = AgentExecution.objects.filter(
                resource=resource, started_at__date=today
            )
            total    = execs.count()
            success  = execs.filter(status="success").count()
            failed   = execs.filter(status="failed").count()
            accuracy = round(success / total * 100, 1) if total > 0 else 0.0
            avg_rt   = int(
                execs.filter(duration_ms__isnull=False)
                     .aggregate(a=Avg("duration_ms"))["a"] or 0
            )
            # simple composite KPI
            kpi = int(
                0.6 * accuracy
                + 0.4 * min(200 / avg_rt, 100) if avg_rt > 0 else 0.6 * accuracy
            )

            results.append(SimpleNamespace(
                resource_id    = resource.id,
                resource       = resource,
                accuracy       = accuracy,
                avg_response_ms= avg_rt,
                kpi_score      = kpi,
                errors_today   = failed,
                tasks_completed= success,
                tasks_failed   = failed,
                tasks_pending  = execs.filter(status__in=["pending","running"]).count(),
                sla_breaches   = 0,
                human_overrides= 0,
                trend          = "+0.0%",
                trend_up       = True,
            ))

        return results

    # ── Placeholder fallback: zero rows so UI can render agent names ──────
    def _build_placeholder_stats(self):
        """
        If there are zero executions too, still return one row per agent
        with all-zero values so the compare chart renders the agent names.
        """
        from types import SimpleNamespace

        resources = Resource.objects.filter(type__iexact="AI Agent")
        return [
            SimpleNamespace(
                resource_id    = r.id,
                resource       = r,
                accuracy       = 0.0,
                avg_response_ms= 0,
                kpi_score      = 0,
                errors_today   = 0,
                tasks_completed= 0,
                tasks_failed   = 0,
                tasks_pending  = 0,
                sla_breaches   = 0,
                human_overrides= 0,
                trend          = "+0.0%",
                trend_up       = True,
            )
            for r in resources
        ]


# ─────────────────────────────────────────────────────────────────────────────
# 5.  HITL Feedback
# ─────────────────────────────────────────────────────────────────────────────
class HITLViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    def list(self, request):
        limit         = int(request.query_params.get("limit", 20))
        offset        = int(request.query_params.get("offset", 0))
        action_filter = request.query_params.get("action")
        impact_filter = request.query_params.get("impact")

        qs = HITLFeedback.objects.select_related("resource", "supervisor")
        if action_filter:
            qs = qs.filter(action=action_filter)
        if impact_filter:
            qs = qs.filter(impact=impact_filter)

        total = qs.count()
        page  = qs[offset: offset + limit]
        return Response({"count": total, "results": HITLFeedbackSerializer(page, many=True).data})

    def create(self, request):
        serializer = HITLFeedbackSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        fb = serializer.save(
            supervisor=request.user if request.user.is_authenticated else None,
            supervisor_name=(
                request.user.get_full_name() or request.user.username
                if request.user.is_authenticated
                else request.data.get("supervisor_name", "System")
            ),
        )
        return Response(HITLFeedbackSerializer(fb).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        by_action = HITLFeedback.objects.values("action").annotate(count=Count("id"))
        by_impact = HITLFeedback.objects.values("impact").annotate(count=Count("id"))
        by_agent  = (
            HITLFeedback.objects.values("agent_name")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        )
        return Response({
            "total":     HITLFeedback.objects.count(),
            "by_action": {r["action"]: r["count"] for r in by_action},
            "by_impact": {r["impact"]: r["count"] for r in by_impact},
            "by_agent":  list(by_agent),
        })


# ─────────────────────────────────────────────────────────────────────────────
# 6.  Weekly task counts
# ─────────────────────────────────────────────────────────────────────────────
class WeeklyTaskViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    def list(self, request):
        agent_id = request.query_params.get("agent")
        qs       = AgentWeeklyTask.objects.select_related("resource")
        if agent_id:
            qs = qs.filter(resource_id=agent_id)
        return Response(AgentWeeklyTaskSerializer(qs, many=True).data)


# ─────────────────────────────────────────────────────────────────────────────
# 7.  Stats sync
# ─────────────────────────────────────────────────────────────────────────────
class StatsSyncViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    def create(self, request):
        raw_date = request.data.get("date")
        try:
            sync_date = date.fromisoformat(raw_date) if raw_date else date.today()
        except ValueError:
            return Response(
                {"error": f"Invalid date: '{raw_date}'. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            service = AnalyticsSyncService()
            report  = service.sync_date(sync_date)
            return Response({"success": True, "date": str(sync_date), "report": report})
        except Exception as exc:
            logger.exception("Stats sync failed")
            return Response({"error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
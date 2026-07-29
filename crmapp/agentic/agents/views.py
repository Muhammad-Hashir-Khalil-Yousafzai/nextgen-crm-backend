"""
crmapp/agentic/agents/views.py

API endpoints consumed by the Autonomous Agents frontend.

Endpoints (all at /api/agentic/agents/):
  GET    resources/                     → list all agents (Resource rows)
  POST   resources/create_agent/        → create custom agent (Agent Builder)
  GET    resources/{id}/                → single agent detail
  PUT    resources/{id}/                → update agent
  DELETE resources/{id}/                → delete agent
  POST   resources/{id}/test_agent/     → run quick Groq test
  GET    resources/available_tools/     → list all registered tools

  GET    history/recent/                → last 50 executions (activity log)
  GET    alerts/active/                 → active bottleneck alerts
  POST   alerts/{id}/resolve/           → resolve an alert

  GET    performance/                   → monthly performance stats
"""

import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from crmapp.agentic.core.models import Resource
from .models import AgentConfig, AgentExecution, AgentTool, AgentMemory
from .serializers import (
    ResourceSerializer,
    AgentExecutionSerializer,
    AgentToolSerializer,
)
from .services import (
    create_agent_from_payload,
    test_agent_with_groq,
    run_agent_task,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Resource ViewSet — /api/agentic/agents/resources/
# ─────────────────────────────────────────────────────────────────────────────

class ResourceViewSet(viewsets.ModelViewSet):
    """
    Handles all agent (Resource) CRUD + custom actions.
    AllowAny for now — add authentication later.
    """
    queryset           = Resource.objects.all().order_by("name")
    serializer_class   = ResourceSerializer
    permission_classes = [AllowAny]

    # ── List all agents ──────────────────────────────────────────────────────
    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    # ── Single agent ─────────────────────────────────────────────────────────
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        return Response(self.get_serializer(instance).data)

    # ── Delete agent ─────────────────────────────────────────────────────────
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        name = instance.name
        instance.delete()
        return Response(
            {"message": f"Agent '{name}' deleted."},
            status=status.HTTP_200_OK,
        )

    # ── POST /resources/create_agent/ ────────────────────────────────────────
    @action(detail=False, methods=["post"], url_path="create_agent")
    def create_agent(self, request):
        """
        Create a custom agent from Agent Builder form.

        Expected body:
          {
            "name": "Invoice Collector Agent",
            "role": "Finance Specialist",
            "goal": "Recover overdue invoices",
            "backstory": "...",
            "tools": ["Web Search", "Email Send"],
            "dept": "Finance",
            "metadata_extra": {
              "skills": ["Invoice Monitor", "Email Sequence"],
              "llm": "groq/llama-3.3-70b-versatile",
              "temperature": 0.3,
              "max_tokens": 1024,
              "color": "#f97316",
              "priority": "high"
            }
          }
        """
        data = request.data

        if not data.get("name"):
            return Response(
                {"error": "Agent name is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not data.get("role"):
            return Response(
                {"error": "Role is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not data.get("goal"):
            return Response(
                {"error": "Goal is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            resource = create_agent_from_payload(data)
            serializer = ResourceSerializer(resource)
            return Response(
                {
                    "success": True,
                    "agent":   serializer.data,
                    "message": f"Agent '{resource.name}' deployed successfully.",
                },
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
            logger.error(f"create_agent failed: {e}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # ── POST /resources/{id}/test_agent/ ─────────────────────────────────────
    @action(detail=True, methods=["post"], url_path="test_agent")
    def test_agent(self, request, pk=None):
        """
        Quick Groq test for an agent. No CrewAI overhead.

        Optional body:
          { "prompt": "Custom test prompt here..." }
        """
        resource = self.get_object()
        prompt   = request.data.get("prompt", None)

        result = test_agent_with_groq(resource, prompt=prompt)
        return Response(result)

    # ── POST /resources/{id}/run_task/ ───────────────────────────────────────
    @action(detail=True, methods=["post"], url_path="run_task")
    def run_task(self, request, pk=None):
        """
        Run a full CrewAI task with this agent.

        Body:
          {
            "task_name": "Research competitors",
            "task_description": "Find top 5 competitors of Acme Corp..."
          }
        """
        resource         = self.get_object()
        task_name        = request.data.get("task_name", "Agent Task")
        task_description = request.data.get("task_description", "")

        if not task_description:
            return Response(
                {"error": "task_description is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Mark resource as busy
        resource.status = "busy"
        resource.current_load += 1
        resource.update_load()
        resource.save(update_fields=["status", "current_load"])

        result = run_agent_task(resource, task_name, task_description)

        # Mark back to idle
        resource.status = "idle"
        resource.save(update_fields=["status"])

        return Response(result)

    # ── GET /resources/available_tools/ ──────────────────────────────────────
    @action(detail=False, methods=["get"], url_path="available_tools")
    def available_tools(self, request):
        """Returns all registered tools from the AgentTool table."""
        tools = AgentTool.objects.filter(is_active=True)
        serializer = AgentToolSerializer(tools, many=True)
        return Response(serializer.data)


# ─────────────────────────────────────────────────────────────────────────────
# History ViewSet — /api/agentic/agents/history/
# ─────────────────────────────────────────────────────────────────────────────

class HistoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset           = AgentExecution.objects.all().order_by("-started_at")
    serializer_class   = AgentExecutionSerializer
    permission_classes = [AllowAny]

    @action(detail=False, methods=["get"], url_path="recent")
    def recent(self, request):
        """Returns last 50 agent executions for the Activity Log tab."""
        qs = self.get_queryset()[:50]
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)


# ─────────────────────────────────────────────────────────────────────────────
# Alerts ViewSet — /api/agentic/agents/alerts/
# Reuses BottleneckAlert from the tasks app
# ─────────────────────────────────────────────────────────────────────────────

class AlertsViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    def _get_alert_model(self):
        from crmapp.agentic.tasks.models import BottleneckAlert
        return BottleneckAlert

    @action(detail=False, methods=["get"], url_path="active")
    def active(self, request):
        """Returns all active (unresolved) alerts."""
        Alert = self._get_alert_model()
        alerts = Alert.objects.filter(resolved_at__isnull=True).order_by("-created_at")
        data = [
            {
                "id":          str(a.id),
                "task_name":   a.task_name,
                "issue":       a.issue,
                "impact":      a.impact,
                "severity":    a.severity,
                "resolved_at": a.resolved_at,
                "created_at":  str(a.created_at),
            }
            for a in alerts
        ]
        return Response(data)

    @action(detail=True, methods=["post"], url_path="resolve")
    def resolve(self, request, pk=None):
        """Marks an alert as resolved."""
        from datetime import datetime, timezone
        Alert = self._get_alert_model()
        try:
            alert = Alert.objects.get(pk=pk)
            alert.resolved_at = datetime.now(timezone.utc)
            note = request.data.get("note", "")
            if hasattr(alert, "resolution_note"):
                alert.resolution_note = note
            alert.save()
            return Response({"success": True, "message": "Alert resolved."})
        except Alert.DoesNotExist:
            return Response(
                {"error": "Alert not found."},
                status=status.HTTP_404_NOT_FOUND,
            )


# ─────────────────────────────────────────────────────────────────────────────
# Performance ViewSet — /api/agentic/agents/performance/
# ─────────────────────────────────────────────────────────────────────────────

class PerformanceViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    def list(self, request):
        """Returns aggregated execution stats."""
        from django.db.models import Count, Avg

        total    = AgentExecution.objects.count()
        success  = AgentExecution.objects.filter(status="success").count()
        failed   = AgentExecution.objects.filter(status="failed").count()
        avg_dur  = AgentExecution.objects.filter(
            duration_ms__isnull=False
        ).aggregate(avg=Avg("duration_ms"))["avg"] or 0

        success_rate = round((success / total * 100), 1) if total > 0 else 0

        return Response({
            "total_executions": total,
            "success":          success,
            "failed":           failed,
            "success_rate":     success_rate,
            "avg_duration_ms":  round(avg_dur, 0),
        })
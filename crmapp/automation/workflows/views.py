"""
crmapp/workflows/views.py

All REST API endpoints — fully working, no stubs.

  WorkflowViewSet
    GET    /api/workflows/                              list all
    POST   /api/workflows/                              create
    GET    /api/workflows/{id}/                         detail with nodes+edges
    PATCH  /api/workflows/{id}/                         update name/status/category
    DELETE /api/workflows/{id}/                         delete
    POST   /api/workflows/{id}/canvas/                  save nodes + edges
    POST   /api/workflows/{id}/run/                     manual trigger
    POST   /api/workflows/{id}/stop/                    stop & pause
    POST   /api/workflows/{id}/duplicate/               duplicate
    GET    /api/workflows/{id}/executions/              list executions
    GET    /api/workflows/{id}/versions/                list versions
    POST   /api/workflows/{id}/versions/                save version snapshot
    POST   /api/workflows/{id}/versions/{vid}/restore/  restore version
    GET    /api/workflows/{id}/webhooks/                list webhooks
    POST   /api/workflows/{id}/webhooks/                create webhook

  ExecutionViewSet
    GET    /api/executions/                             all executions (logs tab)
    GET    /api/executions/{id}/                        single + steps
    POST   /api/executions/{id}/approve/                resume approval (approved)
    POST   /api/executions/{id}/reject/                 resume approval (rejected)

  WebhookReceiverView
    POST   /api/webhooks/{secret}/                      external trigger
"""

import json
import logging

from django.db import transaction
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Workflow, WorkflowNode, WorkflowEdge,
    WorkflowExecution, WorkflowVersion, WorkflowWebhook,
)
from .serializers import (
    WorkflowSerializer, WorkflowListSerializer,
    WorkflowExecutionSerializer,
    WorkflowVersionSerializer, WorkflowWebhookSerializer,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# WORKFLOW VIEWSET
# ─────────────────────────────────────────────────────────────────────────────

class WorkflowViewSet(viewsets.ModelViewSet):
    queryset           = Workflow.objects.all()
    permission_classes = [AllowAny]

    def get_serializer_class(self):
        return WorkflowListSerializer if self.action == "list" else WorkflowSerializer

    # ── Canvas save ───────────────────────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="canvas")
    def save_canvas(self, request, pk=None):
        """
        POST /api/workflows/{id}/canvas/
        Body: { "nodes": [...], "edges": [...] }

        Atomically replaces all nodes and edges.
        Node:  { id, type, label, x, y, config? }
        Edge:  { id, from, to, label? }
        """
        workflow   = self.get_object()
        nodes_data = request.data.get("nodes", [])
        edges_data = request.data.get("edges", [])

        with transaction.atomic():
            workflow.nodes.all().delete()

            node_map = {}
            for nd in nodes_data:
                node = WorkflowNode.objects.create(
                    workflow = workflow,
                    type     = nd.get("type", "action"),
                    label    = nd.get("label", "Node"),
                    x        = float(nd.get("x", 100)),
                    y        = float(nd.get("y", 100)),
                    config   = nd.get("config") or {},
                )
                # Map both the frontend id and new DB id
                node_map[nd.get("id", "")] = node
                node_map[node.id]          = node

            for ed in edges_data:
                fn = node_map.get(ed.get("from")) or node_map.get(ed.get("from_node_id"))
                tn = node_map.get(ed.get("to"))   or node_map.get(ed.get("to_node_id"))
                if fn and tn and fn != tn:
                    WorkflowEdge.objects.get_or_create(
                        workflow  = workflow,
                        from_node = fn,
                        to_node   = tn,
                        defaults  = {"label": ed.get("label", "")},
                    )

        workflow.updated_at = timezone.now()
        workflow.save(update_fields=["updated_at"])

        return Response({
            "success":     True,
            "nodes_saved": len(nodes_data),
            "edges_saved": len(edges_data),
        })

    # ── Manual run ────────────────────────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="run")
    def run(self, request, pk=None):
        """
        POST /api/workflows/{id}/run/
        Body (optional): { "trigger_data": { "amount": 7000, "territory": "North" } }
        """
        from .tasks import execute_workflow_node

        workflow     = self.get_object()
        trigger_data = request.data.get("trigger_data") or {}

        if not workflow.nodes.filter(type="trigger").exists():
            return Response(
                {"error": "Workflow has no trigger node. Add one on the canvas first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        execution = WorkflowExecution.objects.create(
            workflow     = workflow,
            status       = "pending",
            trigger      = "manual",
            trigger_data = trigger_data,
            steps_total  = workflow.nodes.count(),
        )

        transaction.on_commit(lambda: execute_workflow_node.delay(execution.id))

        return Response({
            "success":      True,
            "execution_id": execution.id,
            "message":      f"'{workflow.name}' started. Track it at /api/executions/{execution.id}/",
        }, status=status.HTTP_202_ACCEPTED)

    # ── Stop workflow ─────────────────────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="stop")
    def stop(self, request, pk=None):
        """
        POST /api/workflows/{id}/stop/

        Sets the workflow status to 'paused' and marks any running/pending
        executions as 'failed' so polling stops on the frontend.
        """
        workflow = self.get_object()

        # Kill any in-flight executions
        stopped = WorkflowExecution.objects.filter(
            workflow=workflow,
            status__in=["running", "pending"],
        ).update(
            status      = "failed",
            error       = "Manually stopped by user.",
            finished_at = timezone.now(),
        )

        # Persist workflow status
        workflow.status = "paused"
        workflow.save(update_fields=["status", "updated_at"])

        return Response({
            "success":            True,
            "status":             "paused",
            "executions_stopped": stopped,
        })

    # ── Duplicate ─────────────────────────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="duplicate")
    def duplicate(self, request, pk=None):
        src = self.get_object()

        with transaction.atomic():
            new_wf = Workflow.objects.create(
                name        = f"{src.name} (copy)",
                category    = src.category,
                status      = "draft",
                description = src.description,
            )
            node_map = {}
            for n in src.nodes.all():
                nn = WorkflowNode.objects.create(
                    workflow=new_wf, type=n.type, label=n.label,
                    x=n.x, y=n.y, config=n.config,
                )
                node_map[n.id] = nn

            for e in src.edges.all():
                fn = node_map.get(e.from_node_id)
                tn = node_map.get(e.to_node_id)
                if fn and tn:
                    WorkflowEdge.objects.create(
                        workflow=new_wf, from_node=fn, to_node=tn, label=e.label
                    )

        return Response(
            {"success": True, "workflow": WorkflowListSerializer(new_wf).data},
            status=status.HTTP_201_CREATED,
        )

    # ── Executions list ───────────────────────────────────────────────────────

    @action(detail=True, methods=["get"], url_path="executions")
    def executions(self, request, pk=None):
        workflow = self.get_object()
        qs = workflow.execution_records.order_by("-started_at")[:50]
        return Response([
            {
                "id":          ex.id,
                "status":      ex.status,
                "trigger":     ex.trigger,
                "steps_done":  ex.steps_done,
                "steps_total": ex.steps_total,
                "started_at":  ex.started_at,
                "finished_at": ex.finished_at,
                "duration_ms": ex.duration_ms,
                "error":       ex.error,
            }
            for ex in qs
        ])

    # ── Versions ──────────────────────────────────────────────────────────────

    @action(detail=True, methods=["get", "post"], url_path="versions")
    def versions(self, request, pk=None):
        workflow = self.get_object()

        if request.method == "GET":
            return Response(
                WorkflowVersionSerializer(workflow.versions.all(), many=True).data
            )

        # Save current canvas as a version snapshot
        version_tag = request.data.get("version_tag") or self._next_tag(workflow)
        snapshot    = {
            "nodes": list(workflow.nodes.values("id", "type", "label", "x", "y", "config")),
            "edges": list(workflow.edges.values("id", "from_node_id", "to_node_id", "label")),
        }

        workflow.versions.filter(is_active=True).update(is_active=False)

        version = WorkflowVersion.objects.create(
            workflow    = workflow,
            version_tag = version_tag,
            note        = request.data.get("note", ""),
            author_name = request.data.get("author_name", "System"),
            snapshot    = snapshot,
            is_active   = True,
        )
        return Response(
            WorkflowVersionSerializer(version).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path=r"versions/(?P<version_id>[^/.]+)/restore")
    def restore_version(self, request, pk=None, version_id=None):
        workflow = self.get_object()
        try:
            version = WorkflowVersion.objects.get(id=version_id, workflow=workflow)
        except WorkflowVersion.DoesNotExist:
            return Response({"error": "Version not found."}, status=404)

        snap       = version.snapshot
        node_map   = {}

        with transaction.atomic():
            workflow.nodes.all().delete()
            for nd in snap.get("nodes", []):
                node = WorkflowNode.objects.create(
                    workflow=workflow, type=nd["type"], label=nd["label"],
                    x=nd.get("x", 100), y=nd.get("y", 100), config=nd.get("config", {}),
                )
                node_map[nd["id"]] = node

            for ed in snap.get("edges", []):
                fn = node_map.get(ed.get("from_node_id"))
                tn = node_map.get(ed.get("to_node_id"))
                if fn and tn:
                    WorkflowEdge.objects.create(
                        workflow=workflow, from_node=fn, to_node=tn, label=ed.get("label", "")
                    )

            workflow.versions.filter(is_active=True).update(is_active=False)
            version.is_active = True
            version.save(update_fields=["is_active"])

        return Response({"success": True, "restored_to": version.version_tag})

    # ── Webhooks ──────────────────────────────────────────────────────────────

    @action(detail=True, methods=["get", "post", "delete"], url_path="webhooks")
    def webhooks(self, request, pk=None):
        workflow = self.get_object()

        if request.method == "GET":
            return Response(
                WorkflowWebhookSerializer(
                    workflow.webhooks.all(), many=True, context={"request": request}
                ).data
            )

        if request.method == "POST":
            hook = WorkflowWebhook.objects.create(
                workflow = workflow,
                name     = request.data.get("name", "Default"),
            )
            return Response(
                WorkflowWebhookSerializer(hook, context={"request": request}).data,
                status=status.HTTP_201_CREATED,
            )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _next_tag(self, workflow) -> str:
        latest = workflow.versions.first()
        if not latest:
            return "v1.0"
        try:
            major, minor = latest.version_tag.lstrip("v").split(".")
            return f"v{major}.{int(minor)+1}"
        except Exception:
            return f"v{workflow.versions.count()+1}.0"


# ─────────────────────────────────────────────────────────────────────────────
# EXECUTION VIEWSET
# ─────────────────────────────────────────────────────────────────────────────

class ExecutionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset           = WorkflowExecution.objects.select_related("workflow").order_by("-started_at")
    serializer_class   = WorkflowExecutionSerializer
    permission_classes = [AllowAny]

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()[:100]
        return Response([
            {
                "id":            ex.id,
                "workflow":      ex.workflow_id,
                "workflow_name": ex.workflow.name,
                "status":        ex.status,
                "trigger":       ex.trigger,
                "steps_done":    ex.steps_done,
                "steps_total":   ex.steps_total,
                "started_at":    ex.started_at,
                "finished_at":   ex.finished_at,
                "duration_ms":   ex.duration_ms,
                "error":         ex.error,
            }
            for ex in qs
        ])

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        return self._resume_approval(pk, approved=True, note=request.data.get("note", ""))

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        return self._resume_approval(pk, approved=False, note=request.data.get("note", ""))

    def _resume_approval(self, execution_id: str, approved: bool, note: str = ""):
        from .tasks import execute_workflow_node
        from .executor import WorkflowRunner

        try:
            execution = WorkflowExecution.objects.get(id=execution_id)
        except WorkflowExecution.DoesNotExist:
            return Response({"error": "Execution not found."}, status=404)

        if execution.status != "paused":
            return Response(
                {"error": f"Execution is not paused (status: {execution.status})."},
                status=400,
            )

        approval_node_id = execution.context.get("pending_approval_node")
        if not approval_node_id:
            return Response({"error": "No pending approval node in context."}, status=400)

        # Record decision
        decision = "approved" if approved else "rejected"
        execution.context["approval_decision"] = decision
        execution.context["approval_note"]     = note
        execution.status = "running"
        execution.save(update_fields=["status", "context"])

        # Find next node
        try:
            node   = WorkflowNode.objects.get(id=approval_node_id)
            runner = WorkflowRunner(execution_id)

            # Try labelled branch first
            branch     = "Approved" if approved else "Rejected"
            next_nodes = runner._next_nodes(execution.workflow, node, branch_label=branch)

            # Fall back to any next node
            if not next_nodes:
                next_nodes = runner._next_nodes(execution.workflow, node)

            if next_nodes:
                execute_workflow_node.delay(execution_id, next_nodes[0].id)
            else:
                execution.status      = "success"
                execution.finished_at = timezone.now()
                execution.save(update_fields=["status", "finished_at"])

        except Exception as exc:
            logger.error(f"[Approval] Resume failed: {exc}")
            return Response({"error": str(exc)}, status=500)

        return Response({
            "success":  True,
            "decision": decision,
            "message":  f"Execution {decision} and resumed.",
        })


# ─────────────────────────────────────────────────────────────────────────────
# WEBHOOK RECEIVER
# ─────────────────────────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name="dispatch")
class WebhookReceiverView(APIView):
    """
    POST /api/webhooks/{secret}/

    External systems (CRM, ERP, etc.) call this to trigger a workflow.
    The secret matches WorkflowWebhook.secret.
    Any JSON payload becomes trigger_data in the execution.
    """
    permission_classes = [AllowAny]

    def post(self, request, secret):
        from .tasks import execute_workflow_node

        # Find webhook
        try:
            hook = WorkflowWebhook.objects.select_related("workflow").get(
                secret=secret, is_active=True
            )
        except WorkflowWebhook.DoesNotExist:
            return Response({"error": "Invalid or inactive webhook."}, status=404)

        workflow = hook.workflow
        if workflow.status not in ("active", "draft"):
            return Response(
                {"error": f"Workflow status is '{workflow.status}' — not accepting triggers."},
                status=400,
            )

        # Parse payload
        try:
            trigger_data = (
                request.data if isinstance(request.data, dict)
                else json.loads(request.body)
            )
        except Exception:
            trigger_data = {}

        # Create execution
        execution = WorkflowExecution.objects.create(
            workflow     = workflow,
            status       = "pending",
            trigger      = "webhook",
            trigger_data = trigger_data,
            steps_total  = workflow.nodes.count(),
        )

        # Update webhook stats
        hook.last_fired = timezone.now()
        hook.fire_count += 1
        hook.save(update_fields=["last_fired", "fire_count"])

        # Queue in Celery
        execute_workflow_node.delay(execution.id)

        logger.info(
            f"[Webhook] '{workflow.name}' triggered via {hook.name} → {execution.id}"
        )

        return Response({
            "success":      True,
            "execution_id": execution.id,
            "workflow":     workflow.name,
            "message":      f"Workflow triggered. Track it at /api/executions/{execution.id}/",
        }, status=status.HTTP_202_ACCEPTED)
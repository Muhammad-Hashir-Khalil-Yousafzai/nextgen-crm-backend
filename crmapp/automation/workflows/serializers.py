"""
crmapp/workflows/serializers.py
"""

from rest_framework import serializers
from .models import (
    Workflow, WorkflowNode, WorkflowEdge,
    WorkflowExecution, WorkflowExecutionStep,
    WorkflowVersion, WorkflowWebhook,
)


class WorkflowNodeSerializer(serializers.ModelSerializer):
    class Meta:
        model  = WorkflowNode
        fields = ["id", "type", "label", "x", "y", "config"]


class WorkflowEdgeSerializer(serializers.ModelSerializer):
    from_node_id = serializers.CharField(source="from_node.id", read_only=True)
    to_node_id   = serializers.CharField(source="to_node.id",   read_only=True)

    class Meta:
        model  = WorkflowEdge
        fields = ["id", "from_node_id", "to_node_id", "label"]


class WorkflowSerializer(serializers.ModelSerializer):
    nodes = WorkflowNodeSerializer(many=True, read_only=True)
    edges = WorkflowEdgeSerializer(many=True, read_only=True)

    class Meta:
        model  = Workflow
        fields = [
            "id", "name", "category", "status", "description",
            "executions", "last_run", "created_at", "updated_at",
            "trigger_on_lead_created",
            "nodes", "edges",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "executions", "last_run"]


class WorkflowListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for the sidebar list (no nodes/edges)."""
    node_count = serializers.SerializerMethodField()
    edge_count = serializers.SerializerMethodField()

    class Meta:
        model  = Workflow
        fields = [
            "id", "name", "category", "status",
            "executions", "last_run", "node_count", "edge_count",
            "trigger_on_lead_created",
            "created_at", "updated_at",
        ]

    def get_node_count(self, obj):
        return obj.nodes.count()

    def get_edge_count(self, obj):
        return obj.edges.count()


class WorkflowExecutionStepSerializer(serializers.ModelSerializer):
    node_label = serializers.CharField(source="node.label", read_only=True)
    node_type  = serializers.CharField(source="node.type",  read_only=True)

    class Meta:
        model  = WorkflowExecutionStep
        fields = [
            "id", "node_label", "node_type", "status",
            "output", "branch_taken", "started_at", "finished_at", "duration_ms",
        ]


class WorkflowExecutionSerializer(serializers.ModelSerializer):
    steps        = WorkflowExecutionStepSerializer(many=True, read_only=True)
    workflow_name = serializers.CharField(source="workflow.name", read_only=True)

    class Meta:
        model  = WorkflowExecution
        fields = [
            "id", "workflow", "workflow_name", "status", "trigger",
            "trigger_data", "context", "steps_total", "steps_done",
            "error", "started_at", "finished_at", "duration_ms",
            "steps",
        ]


class WorkflowVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model  = WorkflowVersion
        fields = [
            "id", "version_tag", "note", "author_name",
            "snapshot", "is_active", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class WorkflowWebhookSerializer(serializers.ModelSerializer):
    trigger_url = serializers.SerializerMethodField()

    class Meta:
        model  = WorkflowWebhook
        fields = [
            "id", "name", "secret", "is_active",
            "last_fired", "fire_count", "created_at", "trigger_url",
        ]
        read_only_fields = ["id", "secret", "created_at", "fire_count", "last_fired"]

    def get_trigger_url(self, obj):
        request = self.context.get("request")
        path    = f"/api/workflows/webhooks/{obj.secret}/"
        if request:
            return request.build_absolute_uri(path)
        return path
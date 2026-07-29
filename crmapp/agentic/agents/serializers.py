"""
crmapp/agentic/agents/serializers.py
"""

from rest_framework import serializers
from crmapp.agentic.core.models import Resource
from .models import AgentConfig, AgentExecution, AgentTool, AgentMemory


class AgentConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model  = AgentConfig
        fields = [
            "id", "llm", "temperature", "max_tokens",
            "skills", "dept", "priority", "created_at",
        ]


class ResourceSerializer(serializers.ModelSerializer):
    """
    Full agent serializer — matches exactly what the frontend expects.
    The frontend reads: id, name, type, status, color, metadata,
    load_percentage, last_heartbeat, tools.
    """
    config = AgentConfigSerializer(read_only=True)

    class Meta:
        model  = Resource
        fields = [
        "id", "name", "type", "status",
        "capacity", "current_load", "load_percentage",
        "role", "goal", "backstory",
        "tools", "color", "metadata",
        "last_heartbeat",
        "config",
    ]


class AgentExecutionSerializer(serializers.ModelSerializer):
    """
    Serializer for the activity log (History tab).
    Frontend reads: id, task_name, agent, dept, status, started_at, duration_ms
    """
    agent = serializers.SerializerMethodField()

    class Meta:
        model  = AgentExecution
        fields = [
            "id", "task_name", "agent", "dept",
            "status", "result", "error",
            "started_at", "finished_at", "duration_ms",
            "tools_used",
        ]

    def get_agent(self, obj):
        try:
            # Check if a resource ID exists first without forcing the DB fetch immediately
            return obj.resource.name if obj.resource_id else "—"
        except Resource.DoesNotExist:
            return "Deleted Agent"

class AgentToolSerializer(serializers.ModelSerializer):
    class Meta:
        model  = AgentTool
        fields = ["id", "tool_id", "name", "icon", "category", "description", "is_active"]


class AgentMemorySerializer(serializers.ModelSerializer):
    class Meta:
        model  = AgentMemory
        fields = ["id", "memory_type", "key", "value", "importance", "expires_at", "created_at"]
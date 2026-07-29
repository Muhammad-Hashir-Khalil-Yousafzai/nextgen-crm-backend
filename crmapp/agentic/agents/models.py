import uuid
from django.db import models
from crmapp.agentic.core.models import Resource


def make_config_id():
    return f"cfg-{uuid.uuid4().hex[:6]}"

def make_exec_id():
    return f"exec-{uuid.uuid4().hex[:6]}"

def make_tool_id():
    return f"tool-{uuid.uuid4().hex[:6]}"

def make_mem_id():
    return f"mem-{uuid.uuid4().hex[:6]}"


class AgentConfig(models.Model):
    LLM_CHOICES = [
        ("groq/llama-3.3-70b-versatile", "Llama 3.3 70B"),
        ("groq/llama-3.1-8b-instant",    "Llama 3.1 8B"),
        ("groq/mixtral-8x7b-32768",      "Mixtral 8x7B"),
        ("groq/gemma2-9b-it",            "Gemma 2 9B"),
    ]

    id          = models.CharField(max_length=50, primary_key=True, default=make_config_id)
    resource    = models.OneToOneField(
        Resource,
        on_delete=models.CASCADE,
        related_name="config",
    )
    llm         = models.CharField(max_length=100, choices=LLM_CHOICES, default="groq/llama-3.3-70b-versatile")
    temperature = models.FloatField(default=0.3)
    max_tokens  = models.IntegerField(default=1024)
    skills      = models.JSONField(default=list, blank=True)
    dept        = models.CharField(max_length=100, default="General")

    PRIORITY_CHOICES = [
        ("critical", "Critical"),
        ("high",     "High"),
        ("normal",   "Normal"),
        ("low",      "Low"),
    ]
    priority    = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="normal")
    extra       = models.JSONField(default=dict, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "agent_configs"

    def __str__(self):
        return f"Config for {self.resource.name}"


class AgentTool(models.Model):
    CATEGORY_CHOICES = [
        ("Research",      "Research"),
        ("Communication", "Communication"),
        ("CRM",           "CRM"),
        ("Productivity",  "Productivity"),
        ("Data",          "Data"),
    ]

    id           = models.CharField(max_length=50, primary_key=True, default=make_tool_id)
    tool_id      = models.CharField(max_length=100, unique=True)
    name         = models.CharField(max_length=200)
    icon         = models.CharField(max_length=10, default="🔧")
    category     = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    description  = models.TextField(blank=True)
    is_active    = models.BooleanField(default=True)
    requires_key = models.CharField(max_length=100, blank=True, default="")
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agent_tools"
        ordering = ["category", "name"]

    def __str__(self):
        return self.name


class AgentExecution(models.Model):
    STATUS_CHOICES = [
        ("running", "Running"),
        ("success", "Success"),
        ("failed",  "Failed"),
        ("pending", "Pending"),
    ]

    id          = models.CharField(max_length=50, primary_key=True, default=make_exec_id)
    resource    = models.ForeignKey(
        Resource,
        on_delete=models.SET_NULL,
        null=True,
        related_name="executions",
    )
    task_name   = models.CharField(max_length=300)
    task_input  = models.TextField(blank=True, default="")
    dept        = models.CharField(max_length=100, blank=True, default="")
    goal_id     = models.CharField(max_length=50, blank=True, default="") 
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    result      = models.TextField(blank=True, default="")
    error       = models.TextField(blank=True, default="")
    started_at  = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.IntegerField(null=True, blank=True)
    tools_used  = models.JSONField(default=list, blank=True)
    raw_output  = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "agent_executions"
        ordering = ["-started_at"]

    def __str__(self):
        agent = self.resource.name if self.resource else "Unknown"
        return f"{agent} → {self.task_name} [{self.status}]"

    @property
    def agent(self):
        return self.resource.name if self.resource else "—"


class AgentMemory(models.Model):
    MEMORY_TYPES = [
        ("short_term", "Short Term"),
        ("long_term",  "Long Term"),
        ("episodic",   "Episodic"),
    ]

    id          = models.CharField(max_length=50, primary_key=True, default=make_mem_id)
    resource    = models.ForeignKey(
        Resource,
        on_delete=models.CASCADE,
        related_name="memories",
    )
    memory_type = models.CharField(max_length=20, choices=MEMORY_TYPES, default="short_term")
    key         = models.CharField(max_length=200)
    value       = models.TextField()
    importance  = models.FloatField(default=0.5)
    expires_at  = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agent_memories"
        ordering = ["-importance", "-created_at"]
        unique_together = [["resource", "key"]]

    def __str__(self):
        return f"{self.resource.name}: {self.key}"
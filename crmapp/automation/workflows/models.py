"""
crmapp/workflows/models.py

Four models power the entire workflow system:

  Workflow             — the workflow definition (name, category, status)
  WorkflowNode         — each node on the canvas (type, position, label)
  WorkflowEdge         — connections between nodes (with optional branch label)
  WorkflowExecution    — one run of a workflow (triggered by webhook or button)
  WorkflowExecutionStep— per-node result within a run (status, output, duration)
  WorkflowVersion      — snapshot of a workflow at a point in time
  WorkflowWebhook      — registered webhooks that can trigger workflows
"""

import uuid
from django.db import models
from django.contrib.auth.models import User


def _wf_id():   return f"wf-{uuid.uuid4().hex[:8]}"
def _nd_id():   return f"nd-{uuid.uuid4().hex[:8]}"
def _ed_id():   return f"ed-{uuid.uuid4().hex[:8]}"
def _ex_id():   return f"ex-{uuid.uuid4().hex[:8]}"
def _st_id():   return f"st-{uuid.uuid4().hex[:8]}"
def _ver_id():  return f"ver-{uuid.uuid4().hex[:8]}"
def _whk_id():  return f"whk-{uuid.uuid4().hex[:8]}"
def _whk_secret(): return uuid.uuid4().hex   

# ── Workflow ──────────────────────────────────────────────────────────────────

class Workflow(models.Model):
    STATUS_CHOICES = [
        ("active",  "Active"),
        ("paused",  "Paused"),
        ("draft",   "Draft"),
        ("archived","Archived"),
    ]
    CATEGORY_CHOICES = [
        ("CRM",       "CRM"),
        ("Finance",   "Finance"),
        ("HR",        "HR"),
        ("Support",   "Support"),
        ("Ops",       "Ops"),
        ("Marketing", "Marketing"),
        ("General",   "General"),
    ]

    id          = models.CharField(max_length=20, primary_key=True, default=_wf_id)
    name        = models.CharField(max_length=255)
    category    = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default="General")
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    description = models.TextField(blank=True, default="")
    created_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    executions  = models.IntegerField(default=0)   # denormalised counter
    last_run    = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)
    trigger_on_lead_created = models.BooleanField(
            default=False,
            help_text="If enabled, this workflow fires automatically whenever a new Lead is created.")
    

    class Meta:
        db_table = "workflows"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.name} [{self.status}]"


# ── WorkflowNode ──────────────────────────────────────────────────────────────

class WorkflowNode(models.Model):
    NODE_TYPES = [
        ("trigger",   "Trigger"),
        ("condition", "Condition"),
        ("action",    "Action"),
        ("delay",     "Delay"),
        ("notify",    "Notify"),
        ("approval",  "Approval"),
        ("end",       "End"),
    ]

    id       = models.CharField(max_length=20, primary_key=True, default=_nd_id)
    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name="nodes")
    type     = models.CharField(max_length=20, choices=NODE_TYPES)
    label    = models.CharField(max_length=255)
    x        = models.FloatField(default=100)
    y        = models.FloatField(default=100)
    # Extra config per node type (delay seconds, condition expression, etc.)
    config   = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "workflow_nodes"

    def __str__(self):
        return f"{self.label} ({self.type})"


# ── WorkflowEdge ──────────────────────────────────────────────────────────────

class WorkflowEdge(models.Model):
    id          = models.CharField(max_length=20, primary_key=True, default=_ed_id)
    workflow    = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name="edges")
    from_node   = models.ForeignKey(WorkflowNode, on_delete=models.CASCADE, related_name="outgoing")
    to_node     = models.ForeignKey(WorkflowNode, on_delete=models.CASCADE, related_name="incoming")
    label       = models.CharField(max_length=100, blank=True, default="")

    class Meta:
        db_table = "workflow_edges"
        unique_together = [["from_node", "to_node"]]

    def __str__(self):
        return f"{self.from_node.label} → {self.to_node.label} [{self.label}]"


# ── WorkflowExecution ─────────────────────────────────────────────────────────

class WorkflowExecution(models.Model):
    STATUS_CHOICES = [
        ("pending",  "Pending"),
        ("running",  "Running"),
        ("success",  "Success"),
        ("failed",   "Failed"),
        ("paused",   "Paused"),   # waiting on approval node
    ]
    TRIGGER_CHOICES = [
        ("manual",   "Manual"),
        ("webhook",  "Webhook"),
        ("schedule", "Schedule"),
    ]

    id           = models.CharField(max_length=20, primary_key=True, default=_ex_id)
    workflow     = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name="execution_records")
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    trigger      = models.CharField(max_length=20, choices=TRIGGER_CHOICES, default="manual")
    trigger_data = models.JSONField(default=dict, blank=True)  # webhook payload etc.
    # Which node are we currently executing
    current_node = models.ForeignKey(
        WorkflowNode, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="active_executions"
    )
    context      = models.JSONField(default=dict, blank=True)  # data passed node→node
    steps_total  = models.IntegerField(default=0)
    steps_done   = models.IntegerField(default=0)
    error        = models.TextField(blank=True, default="")
    started_at   = models.DateTimeField(auto_now_add=True)
    finished_at  = models.DateTimeField(null=True, blank=True)
    duration_ms  = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "workflow_executions"
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.workflow.name} / {self.id} [{self.status}]"


# ── WorkflowExecutionStep ─────────────────────────────────────────────────────

class WorkflowExecutionStep(models.Model):
    STATUS_CHOICES = [
        ("pending",  "Pending"),
        ("running",  "Running"),
        ("success",  "Success"),
        ("failed",   "Failed"),
        ("skipped",  "Skipped"),
    ]

    id          = models.CharField(max_length=20, primary_key=True, default=_st_id)
    execution   = models.ForeignKey(WorkflowExecution, on_delete=models.CASCADE, related_name="steps")
    node        = models.ForeignKey(WorkflowNode, on_delete=models.CASCADE, related_name="steps")
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    output      = models.TextField(blank=True, default="")
    branch_taken = models.CharField(max_length=100, blank=True, default="")  # for condition nodes
    started_at  = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "workflow_execution_steps"
        ordering = ["started_at"]


# ── WorkflowVersion ───────────────────────────────────────────────────────────

class WorkflowVersion(models.Model):
    id          = models.CharField(max_length=20, primary_key=True, default=_ver_id)
    workflow    = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name="versions")
    version_tag = models.CharField(max_length=20)       # e.g. "v3.2"
    note        = models.CharField(max_length=255, blank=True, default="")
    author      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    author_name = models.CharField(max_length=200, blank=True, default="")
    # Full snapshot of nodes + edges at this point in time
    snapshot    = models.JSONField(default=dict)
    is_active   = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "workflow_versions"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.workflow.name} {self.version_tag}"


# ── WorkflowWebhook ───────────────────────────────────────────────────────────

class WorkflowWebhook(models.Model):
    """
    Registers a webhook URL for a workflow.
    External systems POST to /api/workflows/webhooks/<secret>/
    to trigger the workflow automatically.
    """


    def _whk_secret(): return uuid.uuid4().hex

    id         = models.CharField(max_length=20, primary_key=True, default=_whk_id)
    workflow   = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name="webhooks")
    name       = models.CharField(max_length=100, default="Default")
    secret = models.CharField(max_length=64, unique=True, default=_whk_secret)
    is_active  = models.BooleanField(default=True)
    last_fired = models.DateTimeField(null=True, blank=True)
    fire_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "workflow_webhooks"

    def __str__(self):
        return f"Webhook for {self.workflow.name}"

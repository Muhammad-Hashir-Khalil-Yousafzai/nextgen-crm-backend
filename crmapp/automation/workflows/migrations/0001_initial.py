"""
crmapp/workflows/migrations/0001_initial.py
"""
import crmapp.automation.workflows.models
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [

        # ── Workflow ──────────────────────────────────────────────────────────
        migrations.CreateModel(
            name="Workflow",
            fields=[
                ("id",          models.CharField(default=crmapp.automation.workflows.models._wf_id, max_length=20, primary_key=True)),
                ("name",        models.CharField(max_length=255)),
                ("category",    models.CharField(choices=[("CRM","CRM"),("Finance","Finance"),("HR","HR"),("Support","Support"),("Ops","Ops"),("Marketing","Marketing"),("General","General")], default="General", max_length=50)),
                ("status",      models.CharField(choices=[("active","Active"),("paused","Paused"),("draft","Draft"),("archived","Archived")], default="draft", max_length=20)),
                ("description", models.TextField(blank=True, default="")),
                ("executions",  models.IntegerField(default=0)),
                ("last_run",    models.DateTimeField(blank=True, null=True)),
                ("created_at",  models.DateTimeField(auto_now_add=True)),
                ("updated_at",  models.DateTimeField(auto_now=True)),
                ("created_by",  models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "workflows", "ordering": ["-updated_at"]},
        ),

        # ── WorkflowNode ──────────────────────────────────────────────────────
        migrations.CreateModel(
            name="WorkflowNode",
            fields=[
                ("id",       models.CharField(default=crmapp.automation.workflows.models._nd_id, max_length=20, primary_key=True)),
                ("type",     models.CharField(choices=[("trigger","Trigger"),("condition","Condition"),("action","Action"),("delay","Delay"),("notify","Notify"),("approval","Approval"),("end","End")], max_length=20)),
                ("label",    models.CharField(max_length=255)),
                ("x",        models.FloatField(default=100)),
                ("y",        models.FloatField(default=100)),
                ("config",   models.JSONField(blank=True, default=dict)),
                ("workflow", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="nodes", to="crm_workflows.workflow")),
            ],
            options={"db_table": "workflow_nodes"},
        ),

        # ── WorkflowEdge ──────────────────────────────────────────────────────
        migrations.CreateModel(
            name="WorkflowEdge",
            fields=[
                ("id",        models.CharField(default=crmapp.automation.workflows.models._ed_id, max_length=20, primary_key=True)),
                ("label",     models.CharField(blank=True, default="", max_length=100)),
                ("workflow",  models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="edges",    to="crm_workflows.workflow")),
                ("from_node", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="outgoing", to="crm_workflows.workflownode")),
                ("to_node",   models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="incoming", to="crm_workflows.workflownode")),
            ],
            options={"db_table": "workflow_edges", "unique_together": {("from_node", "to_node")}},
        ),

        # ── WorkflowExecution ─────────────────────────────────────────────────
        migrations.CreateModel(
            name="WorkflowExecution",
            fields=[
                ("id",           models.CharField(default=crmapp.automation.workflows.models._ex_id, max_length=20, primary_key=True)),
                ("status",       models.CharField(choices=[("pending","Pending"),("running","Running"),("success","Success"),("failed","Failed"),("paused","Paused")], default="pending", max_length=20)),
                ("trigger",      models.CharField(choices=[("manual","Manual"),("webhook","Webhook"),("schedule","Schedule")], default="manual", max_length=20)),
                ("trigger_data", models.JSONField(blank=True, default=dict)),
                ("context",      models.JSONField(blank=True, default=dict)),
                ("steps_total",  models.IntegerField(default=0)),
                ("steps_done",   models.IntegerField(default=0)),
                ("error",        models.TextField(blank=True, default="")),
                ("started_at",   models.DateTimeField(auto_now_add=True)),
                ("finished_at",  models.DateTimeField(blank=True, null=True)),
                ("duration_ms",  models.IntegerField(blank=True, null=True)),
                ("workflow",     models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="execution_records", to="crm_workflows.workflow")),
                ("current_node", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="active_executions", to="crm_workflows.workflownode")),
            ],
            options={"db_table": "workflow_executions", "ordering": ["-started_at"]},
        ),

        # ── WorkflowExecutionStep ─────────────────────────────────────────────
        migrations.CreateModel(
            name="WorkflowExecutionStep",
            fields=[
                ("id",           models.CharField(default=crmapp.automation.workflows.models._st_id, max_length=20, primary_key=True)),
                ("status",       models.CharField(choices=[("pending","Pending"),("running","Running"),("success","Success"),("failed","Failed"),("skipped","Skipped")], default="pending", max_length=20)),
                ("output",       models.TextField(blank=True, default="")),
                ("branch_taken", models.CharField(blank=True, default="", max_length=100)),
                ("started_at",   models.DateTimeField(auto_now_add=True)),
                ("finished_at",  models.DateTimeField(blank=True, null=True)),
                ("duration_ms",  models.IntegerField(blank=True, null=True)),
                ("execution",    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="steps", to="crm_workflows.workflowexecution")),
                ("node",         models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="steps", to="crm_workflows.workflownode")),
            ],
            options={"db_table": "workflow_execution_steps", "ordering": ["started_at"]},
        ),

        # ── WorkflowVersion ───────────────────────────────────────────────────
        migrations.CreateModel(
            name="WorkflowVersion",
            fields=[
                ("id",          models.CharField(default=crmapp.automation.workflows.models._ver_id, max_length=20, primary_key=True)),
                ("version_tag", models.CharField(max_length=20)),
                ("note",        models.CharField(blank=True, default="", max_length=255)),
                ("author_name", models.CharField(blank=True, default="", max_length=200)),
                ("snapshot",    models.JSONField(default=dict)),
                ("is_active",   models.BooleanField(default=False)),
                ("created_at",  models.DateTimeField(auto_now_add=True)),
                ("workflow",    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="versions", to="crm_workflows.workflow")),
                ("author",      models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "workflow_versions", "ordering": ["-created_at"]},
        ),

        # ── WorkflowWebhook ───────────────────────────────────────────────────
        migrations.CreateModel(
            name="WorkflowWebhook",
            fields=[
                ("id",         models.CharField(default=crmapp.automation.workflows.models._whk_id, max_length=20, primary_key=True)),
                ("name",       models.CharField(default="Default", max_length=100)),
                ("secret",     models.CharField(max_length=64, unique=True)),
                ("is_active",  models.BooleanField(default=True)),
                ("last_fired", models.DateTimeField(blank=True, null=True)),
                ("fire_count", models.IntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("workflow",   models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="webhooks", to="crm_workflows.workflow")),
            ],
            options={"db_table": "workflow_webhooks"},
        ),
    ]

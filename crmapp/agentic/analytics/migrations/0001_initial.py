# Generated migration for crmapp/agentic/analytics

import crmapp.agentic.analytics.models
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("agentic_core", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── AgentKPI ──────────────────────────────────────────────────────────
        migrations.CreateModel(
            name="AgentKPI",
            fields=[
                ("id",          models.CharField(default=crmapp.agentic.analytics.models.make_kpi_id,    max_length=50, primary_key=True, serialize=False)),
                ("scope",       models.CharField(choices=[("agent","Per Agent"),("global","Fleet-Wide")], default="agent", max_length=10)),
                ("label",       models.CharField(max_length=200)),
                ("target",      models.FloatField()),
                ("actual",      models.FloatField()),
                ("unit",        models.CharField(blank=True, default="", max_length=20)),
                ("invert",      models.BooleanField(default=False)),
                ("recorded_at", models.DateTimeField(auto_now=True)),
                ("resource",    models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="kpis",
                    to="agentic_core.resource",
                )),
            ],
            options={"db_table": "agent_kpis", "ordering": ["label"],
                     "unique_together": {("resource", "label")}},
        ),

        # ── AgentDailyStat ────────────────────────────────────────────────────
        migrations.CreateModel(
            name="AgentDailyStat",
            fields=[
                ("id",              models.CharField(default=crmapp.agentic.analytics.models.make_stat_id, max_length=50, primary_key=True, serialize=False)),
                ("date",            models.DateField()),
                ("tasks_completed", models.IntegerField(default=0)),
                ("tasks_pending",   models.IntegerField(default=0)),
                ("tasks_failed",    models.IntegerField(default=0)),
                ("errors_today",    models.IntegerField(default=0)),
                ("human_overrides", models.IntegerField(default=0)),
                ("sla_breaches",    models.IntegerField(default=0)),
                ("accuracy",        models.FloatField(default=0.0)),
                ("avg_response_ms", models.IntegerField(default=0)),
                ("kpi_score",       models.IntegerField(default=0)),
                ("trend",           models.CharField(blank=True, default="", max_length=20)),
                ("trend_up",        models.BooleanField(default=True)),
                ("created_at",      models.DateTimeField(auto_now_add=True)),
                ("resource",        models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="daily_stats",
                    to="agentic_core.resource",
                )),
            ],
            options={"db_table": "agent_daily_stats", "ordering": ["-date"],
                     "unique_together": {("resource", "date")}},
        ),

        # ── HITLFeedback ──────────────────────────────────────────────────────
        migrations.CreateModel(
            name="HITLFeedback",
            fields=[
                ("id",              models.CharField(default=crmapp.agentic.analytics.models.make_hitl_id, max_length=50, primary_key=True, serialize=False)),
                ("agent_name",      models.CharField(max_length=200)),
                ("supervisor_name", models.CharField(blank=True, default="", max_length=200)),
                ("action",          models.CharField(choices=[("Override","Override"),("Approved","Approved"),("Correction","Correction")], max_length=20)),
                ("reason",          models.TextField()),
                ("impact",          models.CharField(choices=[("positive","Positive"),("neutral","Neutral"),("negative","Negative")], default="neutral", max_length=20)),
                ("execution_id",    models.CharField(blank=True, default="", max_length=50)),
                ("created_at",      models.DateTimeField(auto_now_add=True)),
                ("resource",        models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="hitl_feedback",
                    to="agentic_core.resource",
                )),
                ("supervisor",      models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="hitl_actions",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"db_table": "hitl_feedback", "ordering": ["-created_at"]},
        ),

        # ── AgentWeeklyTask ───────────────────────────────────────────────────
        migrations.CreateModel(
            name="AgentWeeklyTask",
            fields=[
                ("id",         models.CharField(default=crmapp.agentic.analytics.models.make_weekly_id, max_length=50, primary_key=True, serialize=False)),
                ("counts",     models.JSONField(default=list)),
                ("week_end",   models.DateField()),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("resource",   models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="weekly_tasks",
                    to="agentic_core.resource",
                )),
            ],
            options={"db_table": "agent_weekly_tasks"},
        ),
    ]

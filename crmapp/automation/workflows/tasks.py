"""
crmapp/workflows/tasks.py

Three Celery tasks:
  execute_workflow_node       — start or resume a workflow execution
  resume_workflow_after_delay — called by Celery countdown after a delay node
  check_scheduled_workflows   — Beat task, runs every minute
"""

import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    name="workflows.execute_workflow_node",
)
def execute_workflow_node(self, execution_id: str, node_id: str = None):
    """
    Start or continue a workflow execution from node_id.
    Triggered by: manual run, webhook, resume after delay/approval.
    """
    from .executor import WorkflowRunner
    from .models import WorkflowExecution

    try:
        runner = WorkflowRunner(execution_id)
        runner.run(node_id=node_id)

    except Exception as exc:
        logger.error(f"[Celery] execute_workflow_node crashed ({execution_id}): {exc}")
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            try:
                ex = WorkflowExecution.objects.get(id=execution_id)
                ex.status = "failed"
                ex.error  = f"Max retries exceeded: {exc}"
                ex.save(update_fields=["status", "error"])
            except WorkflowExecution.DoesNotExist:
                pass


@shared_task(name="workflows.resume_workflow_after_delay")
def resume_workflow_after_delay(execution_id: str, next_node_id: str = None):
    """
    Called by Celery countdown after a Delay node fires.
    Resumes execution at next_node_id.
    """
    from .models import WorkflowExecution
    from .executor import WorkflowRunner

    try:
        execution = WorkflowExecution.objects.get(id=execution_id)
    except WorkflowExecution.DoesNotExist:
        logger.error(f"[Celery] resume: execution {execution_id} not found")
        return

    if execution.status == "failed":
        logger.warning(f"[Celery] resume: {execution_id} already failed — skipping")
        return

    # Restore running status before resuming
    execution.status = "running"
    execution.save(update_fields=["status"])

    logger.info(f"[Celery] Resuming {execution_id} at node {next_node_id}")

    runner = WorkflowRunner(execution_id)
    runner.run(node_id=next_node_id)


@shared_task(name="workflows.check_scheduled_workflows")
def check_scheduled_workflows():
    """
    Celery Beat task — runs every minute.
    Fires workflows whose trigger node has a schedule config.

    Supported schedules (set in trigger node config):
      { "schedule": "every_minute" }
      { "schedule": "every_hour" }
      { "schedule": "every_day" }
      { "schedule": "every_monday" }
      { "schedule": "every_weekday" }   (Mon–Fri)
    """
    from django.utils import timezone
    from .models import Workflow, WorkflowExecution

    now   = timezone.now()
    fired = 0

    for workflow in Workflow.objects.filter(status="active").prefetch_related("nodes"):
        trigger = workflow.nodes.filter(type="trigger").first()
        if not trigger:
            continue

        config   = trigger.config or {}
        schedule = config.get("schedule", "")
        if not schedule:
            continue

        last_run = workflow.last_run
        elapsed  = (now - last_run).total_seconds() if last_run else None

        should_fire = False

        if schedule == "every_minute":
            should_fire = elapsed is None or elapsed >= 60

        elif schedule == "every_hour":
            should_fire = elapsed is None or elapsed >= 3600

        elif schedule == "every_day":
            should_fire = elapsed is None or elapsed >= 86400

        elif schedule == "every_monday":
            should_fire = (
                now.weekday() == 0 and
                (elapsed is None or elapsed >= 86400 * 7)
            )

        elif schedule == "every_weekday":
            should_fire = (
                now.weekday() < 5 and
                (elapsed is None or elapsed >= 86400)
            )

        if not should_fire:
            continue

        execution = WorkflowExecution.objects.create(
            workflow     = workflow,
            status       = "pending",
            trigger      = "schedule",
            trigger_data = {"schedule": schedule, "fired_at": now.isoformat()},
            steps_total  = workflow.nodes.count(),
        )

        execute_workflow_node.delay(execution.id)
        fired += 1
        logger.info(
            f"[Beat] Fired '{workflow.name}' ({schedule}) → {execution.id}"
        )

    return {"fired": fired}

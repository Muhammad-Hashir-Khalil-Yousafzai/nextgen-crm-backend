"""
crmapp/agentic/agents/signals.py
"""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


def get_models():
    from crmapp.agentic.tasks.models import Goal, Task
    return Goal, Task


# ─────────────────────────────────────────────────────────────────────────────
# Signal 1 — Goal reaches 'ready' → auto-dispatch to Celery ONCE
# ─────────────────────────────────────────────────────────────────────────────

def on_goal_parsed(sender, instance, created, **kwargs):
    """
    Fires when a Goal is saved with status='ready'.

    BUG FIXED: The old guard checked:
        if instance.status != "ready": return       ← exits for non-ready
        if instance.status in ("executing", ...): return  ← DEAD CODE

    The second check could never fire because the first already returned
    for any status that isn't "ready". So the signal ALWAYS dispatched when
    the view saved goal.status="ready", causing a double dispatch alongside
    the view's own execute_goal_tasks.delay() call.

    FIX: The execute view sets "_skip_signal_dispatch": True in metadata
    before saving. The signal checks this flag and stands down, letting
    the view's own .delay() call be the single dispatch.
    The signal only dispatches organically (from the parse flow).
    """
    if instance.status != "ready":
        return

    if not instance.structured_tasks:
        return

    # FIX: execute view sets this flag before saving goal.status="ready"
    # so the signal knows the view is already handling the dispatch.
    if instance.metadata.get("_dispatched_by_view"):
        logger.info(
            f"[Signal] Goal {instance.id} — skipping dispatch "
            f"(execute view is handling it)"
        )
        return

    # Guard: if tasks are already running or completed, don't re-dispatch
    try:
        from crmapp.agentic.tasks.models import Task
        already_running = Task.objects.filter(
            metadata__goal_id=str(instance.id),
            status__in=("running", "completed"),
        ).exists()

        if already_running:
            logger.info(
                f"[Signal] Goal {instance.id} already executing — skipping duplicate dispatch"
            )
            return
    except Exception as e:
        logger.warning(f"[Signal] Could not check running tasks for goal {instance.id}: {e}")

    logger.info(f"[Signal] Goal {instance.id} ready — dispatching to Celery")
    try:
        from crmapp.agentic.agents.tasks import execute_goal_tasks
        execute_goal_tasks.delay(str(instance.id))
    except Exception as e:
        logger.error(f"[Signal] Failed to dispatch goal {instance.id}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Signal 2 — Task becomes 'ready' → dispatch standalone tasks only
# ─────────────────────────────────────────────────────────────────────────────

def on_task_ready(sender, instance, created, **kwargs):
    """
    Fires when a Task is saved with status='ready'.
    Skips goal-owned tasks — those are handled by execute_goal_tasks.
    """
    if instance.status != "ready":
        return

    # Skip goal-owned tasks
    if instance.metadata.get("goal_id"):
        return

    logger.info(f"[Signal] Standalone task {instance.id} is ready — finding agent")
    try:
        from crmapp.agentic.agents.tasks import (
            execute_agent_task,
            _find_agent_for_task,
        )

        assignee = instance.assignee or ""
        dept     = instance.dept or ""
        resource = _find_agent_for_task(assignee, dept)

        if resource:
            instance.status = "running"
            instance.save(update_fields=["status"])

            execute_agent_task.delay(
                resource_id=str(resource.id),
                task_name=instance.name,
                task_description=instance.description or instance.name,
                task_id=str(instance.id),
            )
            logger.info(f"[Signal] Task {instance.id} → {resource.name}")
        else:
            reason = (
                f"No agent found — assignee='{assignee}', dept='{dept}'. "
                f"No idle/active agents in DB."
            )
            logger.warning(f"[Signal] {reason}")
            instance.metadata["failure_reason"] = reason
            instance.save(update_fields=["metadata"])

    except Exception as e:
        logger.error(f"[Signal] Failed to handle task ready {instance.id}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Connect signals
# ─────────────────────────────────────────────────────────────────────────────

def connect_signals():
    Goal, Task = get_models()
    post_save.connect(on_goal_parsed, sender=Goal, dispatch_uid="on_goal_parsed")
    post_save.connect(on_task_ready,  sender=Task, dispatch_uid="on_task_ready")
    logger.info("[Signals] Goal and Task signals connected.")
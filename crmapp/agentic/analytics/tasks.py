"""
crmapp/agentic/agents/tasks.py
"""
import traceback
import logging
from celery import shared_task

logger = logging.getLogger(__name__)

AGENT_TYPES = ["AI Agent", "ai_agent"]


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    name="agents.execute_agent_task",
)
def execute_agent_task(
    self,
    resource_id: str,
    task_name: str,
    task_description: str,
    task_id: str = None,
    previous_output: str = None,
):
    from crmapp.agentic.core.models import Resource
    from crmapp.agentic.agents.services import run_agent_task

    logger.info(f"[Celery] Starting '{task_name}' with agent {resource_id}")

    full_description = task_description
    if previous_output:
        full_description = (
            f"{task_description}\n\n"
            f"--- Context from previous agent ---\n"
            f"{previous_output[:1500]}\n"
            f"-----------------------------------\n"
            f"Use the above context to inform your work on this task."
        )

    try:
        resource = Resource.objects.get(id=resource_id)
        resource.status = "busy"
        resource.save(update_fields=["status"])

        result = run_agent_task(resource, task_name, full_description)

        if task_id:
            _update_task_status(
                task_id,
                "completed" if result["success"] else "failed",
                result.get("result", ""),
                failure_reason=result.get("error") if not result["success"] else None,
            )

        resource.status = "idle"
        resource.save(update_fields=["status"])

        logger.info(f"[Celery] '{task_name}' done — success={result['success']}")
        return result

    except Resource.DoesNotExist:
        msg = f"Agent resource_id={resource_id} not found in DB"
        logger.error(f"[Celery] {msg}")
        if task_id:
            _update_task_status(task_id, "failed", msg, failure_reason=msg)
        return {"success": False, "error": msg}

    except Exception as exc:
        logger.error(f"[Celery] Task failed: {exc}")
        logger.error(traceback.format_exc())
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            msg = f"Max retries exceeded: {str(exc)}"
            if task_id:
                _update_task_status(task_id, "failed", msg, failure_reason=msg)
            return {"success": False, "error": msg}


@shared_task(bind=True, name="agents.execute_goal_tasks")
def execute_goal_tasks(self, goal_id: str):
    return _run_goal_execution(goal_id)


def _run_goal_execution(goal_id: str):
    from crmapp.agentic.tasks.models import Goal, Task
    from crmapp.agentic.agents.services import run_agent_task
    from django.db import close_old_connections

    close_old_connections()
    logger.info(f"[Celery] Orchestrating goal {goal_id}")

    try:
        goal = Goal.objects.get(id=goal_id)
        goal.status = "executing"
        goal.save(update_fields=["status"])

        # select_related prevents N+1 queries on depends_on in _build_context
        db_tasks = list(
            Task.objects.filter(
                metadata__goal_id=str(goal_id)
            ).select_related("depends_on").order_by("created_at")
        )

        if not db_tasks:
            logger.warning(f"[Celery] No tasks found for goal {goal_id}")
            goal.status = "failed"
            goal.metadata["execution_summary"] = {"error": "No tasks found for this goal"}
            goal.save()
            return {"success": False, "error": "No tasks found for this goal"}

        execution_order = _topological_sort(db_tasks)
        logger.info(f"[Celery] Execution order: {[t.name for t in execution_order]}")

        completed_outputs = {}
        completed_count = 0
        failed_count = 0

        for task in execution_order:

            # ── Dependency check ──────────────────────────────────────────
            if task.depends_on_id:
                # Re-fetch fresh status — in-memory copy may be stale
                dep = Task.objects.filter(id=task.depends_on_id).first()
                if dep and dep.status != "completed":
                    reason = (
                        f"Blocked: dependency '{dep.name}' "
                        f"has status='{dep.status}' (not completed)"
                    )
                    logger.warning(f"[Celery] Skipping '{task.name}' — {reason}")
                    task.status = "blocked"
                    task.metadata["failure_reason"] = reason
                    task.save(update_fields=["status", "metadata"])
                    failed_count += 1
                    continue

            # ── Find primary agent ────────────────────────────────────────
            resource = _find_agent_for_task(task.assignee or "", task.dept or "")

            if not resource:
                reason = (
                    f"No agent available — assignee='{task.assignee}', "
                    f"dept='{task.dept}'. No idle/active agents found in DB."
                )
                logger.warning(f"[Celery] '{task.name}' — {reason}")
                task.status = "failed"
                task.metadata["failure_reason"] = reason
                task.save(update_fields=["status", "metadata"])
                failed_count += 1
                continue

            # ── Build prompt ──────────────────────────────────────────────
            previous_context = _build_context(task, completed_outputs)
            full_description = task.description or task.name
            if previous_context:
                full_description = (
                    f"{full_description}\n\n"
                    f"--- Context from previous agents ---\n"
                    f"{previous_context}\n"
                    f"------------------------------------\n"
                    f"Use the above context to inform your work."
                )

            task.status = "running"
            task.metadata.pop("failure_reason", None)  # clear any stale failure
            task.save(update_fields=["status", "metadata"])

            logger.info(f"[Celery] Running '{task.name}' → {resource.name}")
            result = run_agent_task(resource, task.name, full_description)

            # ── Backup agent if primary fails ─────────────────────────────
            if not result["success"]:
                logger.warning(
                    f"[Celery] Primary agent '{resource.name}' failed for "
                    f"'{task.name}': {result.get('error')} — trying backup"
                )
                backup = _find_backup_agent(exclude_id=resource.id, dept=task.dept or "")
                if backup:
                    logger.info(f"[Celery] Backup agent '{backup.name}' → '{task.name}'")
                    result = run_agent_task(backup, task.name, full_description)
                    if result["success"]:
                        task.metadata["backup_agent_used"] = backup.name

            # ── Save outcome ──────────────────────────────────────────────
            if result["success"]:
                completed_outputs[task.name] = result.get("result") or ""
                task.status = "completed"
                task.progress = 100
                task.metadata.pop("failure_reason", None)
                task.save(update_fields=["status", "progress", "metadata"])
                completed_count += 1
                logger.info(f"[Celery] ✓ '{task.name}' completed")
            else:
                error_msg = result.get("error", "Unknown error")
                task.status = "failed"
                task.metadata["failure_reason"] = (
                    f"Agent '{resource.name}' failed: {error_msg}"
                )
                task.save(update_fields=["status", "metadata"])
                failed_count += 1
                logger.error(f"[Celery] ✗ '{task.name}' failed: {error_msg}")

        total = len(execution_order)
        goal.status = "completed" if completed_count == total else (
            "completed" if completed_count > 0 else "failed"
        )
        goal.metadata["execution_summary"] = {
            "total":     total,
            "completed": completed_count,
            "failed":    failed_count,
            "progress":  int((completed_count / total) * 100) if total else 0,
        }
        goal.save()

        logger.info(f"[Celery] Goal {goal_id} finished — {completed_count}/{total} completed")
        return {
            "success":   completed_count > 0,
            "goal_id":   goal_id,
            "total":     total,
            "completed": completed_count,
            "failed":    failed_count,
        }

    except Exception as exc:
        logger.error(f"[Celery] execute_goal_tasks crashed: {exc}")
        logger.error(traceback.format_exc())
        try:
            Goal.objects.filter(id=goal_id).update(status="failed")
        except Exception:
            pass
        return {"success": False, "error": str(exc)}


@shared_task(name="agents.check_ready_tasks")
def check_ready_tasks():
    from crmapp.agentic.tasks.models import Task

    # exclude() is safer than isnull=True on JSONField across DB backends
    ready = Task.objects.filter(status="ready").exclude(
        metadata__goal_id__isnull=False
    )

    if not ready.exists():
        return {"checked": 0, "dispatched": 0}

    dispatched = 0
    for task in ready:
        if task.depends_on_id:
            dep = Task.objects.filter(id=task.depends_on_id).first()
            if dep and dep.status != "completed":
                continue

        resource = _find_agent_for_task(task.assignee or "", task.dept or "")
        if not resource:
            continue

        task.status = "running"
        task.save(update_fields=["status"])

        execute_agent_task.delay(
            resource_id=str(resource.id),
            task_name=task.name,
            task_description=task.description or task.name,
            task_id=str(task.id),
        )

        dispatched += 1
        logger.info(f"[Beat] '{task.name}' → {resource.name}")

    return {"checked": ready.count(), "dispatched": dispatched}


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _topological_sort(tasks: list) -> list:
    from collections import deque

    task_map   = {t.id: t for t in tasks}
    in_degree  = {t.id: 0 for t in tasks}
    dependents = {t.id: [] for t in tasks}

    for t in tasks:
        if t.depends_on_id and t.depends_on_id in task_map:
            in_degree[t.id] += 1
            dependents[t.depends_on_id].append(t.id)

    queue   = deque([t for t in tasks if in_degree[t.id] == 0])
    ordered = []

    while queue:
        task = queue.popleft()
        ordered.append(task)
        for dep_id in dependents[task.id]:
            in_degree[dep_id] -= 1
            if in_degree[dep_id] == 0:
                queue.append(task_map[dep_id])

    sorted_ids = {t.id for t in ordered}
    for t in tasks:
        if t.id not in sorted_ids:
            ordered.append(t)

    return ordered


def _build_context(task, completed_outputs: dict) -> str:
    """
    Uses select_related-prefetched depends_on — zero extra DB queries.
    """
    if not task.depends_on_id:
        return ""

    dep = task.depends_on  # already in memory from select_related
    if dep and dep.name in completed_outputs:
        output = completed_outputs[dep.name]
        if output:
            return f"Output from '{dep.name}':\n{output[:1500]}"

    return ""


def _find_agent_for_task(assignee_name: str, dept: str = ""):
    """
    Find best available agent. Handles both 'AI Agent' and 'ai_agent' types.
    """
    from crmapp.agentic.core.models import Resource

    if "(" in assignee_name:
        assignee_name = assignee_name.split("(")[0].strip()

    # 1. Name match
    if assignee_name:
        r = Resource.objects.filter(
            name__icontains=assignee_name,
            status__in=["idle", "active"],
        ).first()
        if r:
            return r

    # 2. Department match
    if dept:
        r = Resource.objects.filter(
            metadata__dept=dept,
            status__in=["idle", "active"],
            type__in=AGENT_TYPES,
        ).order_by("load_percentage").first()
        if r:
            return r

    # 3. Any agent at all (fallback)
    return Resource.objects.filter(
        status__in=["idle", "active"],
        type__in=AGENT_TYPES,
    ).order_by("load_percentage").first()


def _find_backup_agent(exclude_id: str, dept: str = ""):
    """
    Backup agent — excludes the failed primary, tries same dept first.
    """
    from crmapp.agentic.core.models import Resource

    if dept:
        r = Resource.objects.filter(
            metadata__dept=dept,
            status__in=["idle", "active"],
            type__in=AGENT_TYPES,
        ).exclude(id=exclude_id).order_by("load_percentage").first()
        if r:
            return r

    return Resource.objects.filter(
        status__in=["idle", "active"],
        type__in=AGENT_TYPES,
    ).exclude(id=exclude_id).order_by("load_percentage").first()


def _update_task_status(task_id: str, status: str, result: str = "", failure_reason: str = None):
    try:
        from crmapp.agentic.tasks.models import Task
        task = Task.objects.get(id=task_id)
        task.status = status
        if result:
            task.metadata["agent_result"] = result[:500]
        if failure_reason:
            task.metadata["failure_reason"] = failure_reason
        elif status == "completed":
            task.metadata.pop("failure_reason", None)
        task.save(update_fields=["status", "metadata"])
    except Exception as e:
        logger.error(f"Failed to update task {task_id}: {e}")
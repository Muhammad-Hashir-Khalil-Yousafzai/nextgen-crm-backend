"""
crmapp/agentic/agents/tasks.py

Celery tasks with:
  1. Proper dependency checking — tasks wait for parents to complete
  2. Output chaining — each agent receives previous agent's output as context
  3. Goal-level orchestration — executes tasks in correct dependency order
  4. Wave-based sequential execution — safe on Windows/solo pool
  5. Duplicate execution guard — only blocks if tasks are actively running
"""
import traceback
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# TASK 1 — Execute a single agent task (with optional previous context)
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=1,
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
            )

        resource.status = "idle"
        resource.save(update_fields=["status"])

        logger.info(f"[Celery] '{task_name}' done — success={result['success']}")
        return result

    except Resource.DoesNotExist:
        logger.error(f"[Celery] Resource {resource_id} not found.")
        if task_id:
            _update_task_status(task_id, "failed", "Agent not found")
        return {"success": False, "error": f"Agent {resource_id} not found"}

    except Exception as exc:
        logger.error(f"[Celery] Task failed: {exc}")
        logger.error(traceback.format_exc())
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            if task_id:
                _update_task_status(task_id, "failed", str(exc))
            return {"success": False, "error": str(exc)}


# ─────────────────────────────────────────────────────────────────────────────
# TASK 2 — Orchestrate ALL tasks from a Goal in dependency order
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(name="agents.execute_goal_tasks")
def execute_goal_tasks(goal_id: str):
    """Celery entry point — calls the real function"""
    return _run_goal_execution(goal_id)


def _run_goal_execution(goal_id: str):
    """
    Wave-based execution:
    - Each wave = all tasks whose dependencies are already completed
    - Tasks run sequentially within each wave (safe on Windows/solo pool)
    - Dependent tasks always wait for their parent wave to finish

    FIX 1 (Duplicate dispatch): Use update_fields on goal status to avoid
      re-triggering the post_save signal that also calls execute_goal_tasks.
      Guard checks DB-fresh goal status via .get() not cached instance.

    FIX 2 (Stale dependency cache): dep_status is now always fetched fresh
      from DB using values_list() instead of reading task.depends_on.status
      which is a cached select_related object from the start of the wave.

    FIX 3 (Wrong completion status): Goal is only marked "completed" if ALL
      tasks finished successfully. Partial runs are "failed".
    """
    from crmapp.agentic.tasks.models import Goal, Task
    from crmapp.agentic.agents.services import run_agent_task
    from django.db import close_old_connections

    close_old_connections()

    logger.info(f"[Celery] Orchestrating goal {goal_id}")

    try:
        goal = Goal.objects.get(id=goal_id)

        # ── FIX 1: Duplicate guard — use a DB-level atomic check ─────────
        # Two Celery tasks can both pass a Python-level status check if they
        # read goal.status before either has written "executing" back to DB.
        # update() with a conditional WHERE is atomic and only one wins.
        updated = Goal.objects.filter(
            id=goal_id,
            status__in=["ready", "parsed"],   # only transition from these
        ).update(status="executing")

        if updated == 0:
            # Either already executing, completed, or failed — check which
            goal.refresh_from_db()
            if goal.status == "executing":
                actively_running = Task.objects.filter(
                    metadata__goal_id=str(goal_id),
                    status="running",
                ).exists()
                if actively_running:
                    logger.warning(
                        f"[Celery] Goal {goal_id} already actively executing — skipping duplicate"
                    )
                    return {"success": False, "error": "Duplicate execution prevented"}
                # Executing but no running tasks — stale state, allow retry
                logger.warning(
                    f"[Celery] Goal {goal_id} status=executing but no running tasks — resuming"
                )
            elif goal.status in ("completed", "failed"):
                logger.warning(
                    f"[Celery] Goal {goal_id} already {goal.status} — skipping"
                )
                return {"success": False, "error": f"Goal already {goal.status}"}

        # Reload to get the freshest state after the update
        goal.refresh_from_db()
        # Clean up the view's dispatch flag so it doesn't persist in DB
        if goal.metadata.get("_dispatched_by_view"):
            goal.metadata.pop("_dispatched_by_view")
            Goal.objects.filter(id=goal_id).update(metadata=goal.metadata)


        db_tasks = list(
            Task.objects.filter(
                metadata__goal_id=str(goal_id)
            ).order_by("created_at")   # no select_related — we fetch deps fresh per wave
        )

        if not db_tasks:
            logger.warning(f"[Celery] No tasks found for goal {goal_id}")
            Goal.objects.filter(id=goal_id).update(status="failed")
            return {"success": False, "error": "No tasks found for this goal"}

        total             = len(db_tasks)
        completed_count   = 0
        failed_count      = 0
        completed_outputs = {}

        # ── Wave-based execution loop ─────────────────────────────────────
        max_waves  = total + 1
        wave_index = 0

        while wave_index < max_waves:
            wave_index += 1

            # Always refresh from DB — no cached querysets
            remaining = list(
                Task.objects.filter(
                    metadata__goal_id=str(goal_id)
                ).exclude(
                    status__in=["completed", "failed"]
                )
            )

            if not remaining:
                break

            # Build this wave — tasks ready to run right now
            wave_tasks = []
            for task in remaining:
                if task.status == "running":
                    continue

                if task.depends_on_id:
                    # FIX 2: Always fetch dependency status fresh from DB.
                    # task.depends_on would be a stale cached object from
                    # select_related loaded before the previous wave ran —
                    # it would still show the old status (e.g. "ready")
                    # even after the parent completed in this session.
                    dep_status = Task.objects.filter(
                        id=task.depends_on_id
                    ).values_list("status", flat=True).first()

                    if dep_status != "completed":
                        continue

                required_tool = _infer_required_tool(task)
                resource = _find_agent_for_task(task.assignee or "", task.dept or "", required_tool)
                if not resource:
                    reason = (
                        f"No agent available with required tool: {required_tool}"
                        if required_tool else "No agent available"
                    )
                    logger.warning(f"[Celery] {reason} for '{task.name}' — marking failed")
                    Task.objects.filter(id=task.id).update(
                        status="failed",
                        metadata={**task.metadata, "failure_reason": reason},
                    )
                    failed_count += 1
                    continue
                
                wave_tasks.append((task, resource))


            if not wave_tasks:
                # Check if anything is still running before giving up
                still_running = Task.objects.filter(
                    metadata__goal_id=str(goal_id),
                    status="running",
                ).exists()
                if still_running:
                    import time
                    time.sleep(2)
                    continue

                # Nothing running, nothing ready — check if truly stuck
                blocked_count = Task.objects.filter(
                    metadata__goal_id=str(goal_id),
                    status__in=["blocked", "ready", "pending"],
                ).count()
                if blocked_count > 0:
                    logger.warning(
                        f"[Celery] Goal {goal_id} stuck — {blocked_count} task(s) "
                        f"still blocked/ready but no dependencies completed"
                    )
                break

            logger.info(
                f"[Celery] Wave {wave_index}: {len(wave_tasks)} task(s) — "
                f"{[t.name for t, _ in wave_tasks]}"
            )

            # ── Run all tasks in this wave sequentially ───────────────────
            # Safe on Windows/solo pool — no .get() deadlock risk
            for task, resource in wave_tasks:
                Task.objects.filter(id=task.id).update(status="running")

                # Reload task to get latest metadata for context building
                task.refresh_from_db()

                full_description = _build_description(
                    task, _build_context(task, completed_outputs)
                )

                logger.info(f"[Celery] Running '{task.name}' → {resource.name}")
                result = run_agent_task(resource, task.name, full_description)

                if result["success"]:
                    completed_outputs[task.name] = result.get("result") or ""
                    Task.objects.filter(id=task.id).update(
                        status="completed",
                        progress=100,
                    )
                    completed_count += 1
                    logger.info(f"[Celery] ✓ '{task.name}' completed")
                else:
                    Task.objects.filter(id=task.id).update(status="failed")
                    failed_count += 1
                    logger.error(f"[Celery] ✗ '{task.name}' failed: {result.get('error')}")

                # Rate limit guard — Groq free tier caps at ~12K TPM.
                # 10s between tasks keeps throughput well under the limit.
                import time
                time.sleep(10)

        # ── FIX 3: Accurate final goal status ────────────────────────────
        # Old code: "completed" if completed_count > 0  ← wrong, 1/5 = completed
        # New code: only "completed" if every task succeeded
        if completed_count == total:
            final_status = "completed"
        elif completed_count > 0:
            # Partial success — some tasks ran, some didn't
            final_status = "failed"
            logger.warning(
                f"[Celery] Goal {goal_id} partial: {completed_count}/{total} completed"
            )
        else:
            final_status = "failed"

        goal.refresh_from_db()
        goal.status = final_status
        goal.metadata["execution_summary"] = {
            "total":     total,
            "completed": completed_count,
            "failed":    failed_count,
            "progress":  int((completed_count / total) * 100) if total else 0,
        }
        goal.save()

        logger.info(f"[Celery] Goal {goal_id} done — {completed_count}/{total} completed → {final_status}")

        return {
            "success":   final_status == "completed",
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


# ─────────────────────────────────────────────────────────────────────────────
# TASK 3 — Periodic beat: pick up standalone ready tasks
# ─────────────────────────────────────────────────────────────────────────────
@shared_task(name="agents.promote_scheduled_tasks")
def promote_scheduled_tasks():
    """
    Runs every 60 seconds (same cadence as check_ready_tasks).
    Finds tasks whose scheduled_at time has arrived and promotes them
    from 'scheduled' to 'ready' so check_ready_tasks picks them up on
    its next run and dispatches them to an agent.
    """
    from django.utils import timezone
    from crmapp.agentic.tasks.models import Task

    now = timezone.now()

    due_tasks = Task.objects.filter(
        status="scheduled",
        scheduled_at__isnull=False,
        scheduled_at__lte=now,
    )

    count = due_tasks.count()
    if count == 0:
        return {"promoted": 0}

    promoted_ids = list(due_tasks.values_list("id", flat=True))

    due_tasks.update(status="ready")

    logger.info(f"[Celery] Promoted {count} scheduled task(s) to ready: {promoted_ids}")

    return {"promoted": count, "task_ids": promoted_ids}

@shared_task(name="agents.check_ready_tasks")
def check_ready_tasks():
    """
    Runs every 60 seconds. Picks up standalone tasks (not part of a goal)
    with status='ready' and dispatches them to available agents.
    """
    from crmapp.agentic.tasks.models import Task

    ready = Task.objects.filter(
        status="ready",
        metadata__goal_id__isnull=True,
    )

    # FIX: evaluate count once before the loop — tasks are mutated to
    # "running" inside, so a lazy .count() at the end returns a smaller number
    checked    = ready.count()
    dispatched = 0

    if not checked:
        return {"checked": 0, "dispatched": 0}

    for task in ready:
        if task.depends_on_id:
            dep_status = Task.objects.filter(
                id=task.depends_on_id
            ).values_list("status", flat=True).first()
            if dep_status != "completed":
                continue

        resource = _find_agent_for_task(task.assignee or "", task.dept or "")
        if not resource:
            continue

        Task.objects.filter(id=task.id).update(status="running")

        execute_agent_task.delay(
            resource_id=str(resource.id),
            task_name=task.name,
            task_description=task.description or task.name,
            task_id=str(task.id),
        )

        dispatched += 1
        logger.info(f"[Beat] '{task.name}' → {resource.name}")

    return {"checked": checked, "dispatched": dispatched}


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
    if not task.depends_on_id:
        return ""
    dep_name = getattr(task.depends_on, "name", "")
    if not dep_name:
        # depends_on may not be loaded — fetch name from DB
        from crmapp.agentic.tasks.models import Task
        dep_name = Task.objects.filter(
            id=task.depends_on_id
        ).values_list("name", flat=True).first() or ""
    output = completed_outputs.get(dep_name, "")
    if output:
        return f"Output from '{dep_name}':\n{output[:1500]}"
    return ""

def _infer_required_tool(task) -> str:
    """
    Guess which tool a task actually needs based on its name/description,
    so _find_agent_for_task can reject agents that lack it instead of
    picking any available agent regardless of capability.

    BUG FIX — original keyword list used exact phrases like "create lead"
    and "add lead", which failed to match real task text like "Create new
    lead in CRM" / "Add a new lead named Zain" because of the extra words
    in between. Switched to checking for the presence of both a write-verb
    AND a CRM-noun anywhere in the text, rather than requiring an exact
    adjacent phrase.
    """
    text = f"{task.name} {task.description or ''}".lower()

    write_verbs = ["create", "add", "update", "enter", "fill in", "populate", "write", "insert", "save", "confirm"]
    crm_nouns   = ["lead", "crm", "contact", "deal", "record"]

    has_write_verb = any(v in text for v in write_verbs)
    has_crm_noun   = any(n in text for n in crm_nouns)

    if has_write_verb and has_crm_noun:
        return "CRM Write"

    read_verbs = ["read", "retrieve", "fetch", "count", "compile", "verify", "check", "list", "get"]
    has_read_verb = any(v in text for v in read_verbs)
    if has_read_verb and has_crm_noun:
        return "CRM Read"

    # NEW — Slack/notification detection
    if any(w in text for w in ["slack", "notify", "alert the team", "notification"]):
        return "Slack Notify"

    if any(w in text for w in ["email", "send"]):
        return "Email Send"

    return None


def _build_description(task, previous_context: str) -> str:
    full_description = task.description or task.name
    if previous_context:
        full_description = (
            f"{full_description}\n\n"
            f"--- Context from previous agents ---\n"
            f"{previous_context}\n"
            f"------------------------------------\n"
            f"Use the above context to inform your work."
        )
    return full_description



def _find_agent_for_task(assignee_name: str, dept: str = "", required_tool: str = None):
    from crmapp.agentic.core.models import Resource

    if "(" in assignee_name:
        assignee_name = assignee_name.split("(")[0].strip()

    def _has_tool(resource, tool_name):
        if not tool_name:
            return True
        tools = resource.tools or resource.metadata.get("tools", [])
        return tool_name in tools

    # Level 1 — exact name match (Groq assigned a specific agent)
    if assignee_name:
        r = Resource.objects.filter(
            name__icontains=assignee_name,
            status__in=["idle", "active"],
        ).first()
        if r and _has_tool(r, required_tool):
            return r
        # Level 2 — name not found/wrong tools, infer dept from the name
        inferred_dept = _infer_dept_from_name(assignee_name)
        if inferred_dept:
            candidates = Resource.objects.filter(
                metadata__dept=inferred_dept,
                status__in=["idle", "active"],
            ).order_by("load_percentage")
            for r in candidates:
                if _has_tool(r, required_tool):
                    logger.warning(
                        f"[Agent] '{assignee_name}' unavailable/lacks tools — "
                        f"falling back to dept='{inferred_dept}' agent: {r.name}"
                    )
                    return r

    # Level 3 — explicit dept fallback
    if dept:
        candidates = Resource.objects.filter(
            metadata__dept=dept,
            status__in=["idle", "active"],
        ).order_by("load_percentage")
        for r in candidates:
            if _has_tool(r, required_tool):
                return r

    # Level 4 — any available agent, BUT STILL must have the required tool.
    # Previously this had no tool check at all, which is how a Finance/
    # Invoice agent could get picked for a CRM-write task it couldn't do,
    # causing the agent to hallucinate a nonexistent tool name (crm_create,
    # crm_update) instead of failing cleanly.
    candidates = Resource.objects.filter(
        status__in=["idle", "active"],
        type__in=["AI Agent", "ai_agent"],
    ).order_by("load_percentage")
    for r in candidates:
        if _has_tool(r, required_tool):
            return r

    # No agent anywhere has the required tool — return None so the caller
    # marks the task failed with an honest reason instead of silently
    # assigning a capability-mismatched agent.
    return None


def _infer_dept_from_name(name: str) -> str:
    """Guess dept from agent name so we pick a relevant fallback."""
    n = name.lower()
    if any(w in n for w in ["invoice", "finance", "billing", "recovery", "payment"]):
        return "Finance"
    if any(w in n for w in ["lead", "sales", "intelligence", "outreach"]):
        return "Sales"
    if any(w in n for w in ["support", "triage", "helpdesk", "ticket"]):
        return "Support"
    if any(w in n for w in ["marketing", "campaign", "orchestrator"]):
        return "Marketing"
    if any(w in n for w in ["crm", "churn", "guard", "analytics", "retention"]):
        return "CRM"
    if any(w in n for w in ["hr", "onboarding", "employee"]):
        return "HR"
    return ""


def _update_task_status(task_id: str, status: str, result: str = ""):
    try:
        from crmapp.agentic.tasks.models import Task
        task = Task.objects.get(id=task_id)
        task.status = status
        if result:
            task.metadata["agent_result"] = result[:500]
        task.save(update_fields=["status", "metadata"])
    except Exception as e:
        logger.error(f"Failed to update task {task_id}: {e}")
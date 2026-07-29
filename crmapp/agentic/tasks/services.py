"""
crmapp/agentic/tasks/services.py

FIXES APPLIED:
  Bug (missing return) — build_crewai_agent() never returned the agent object.
                         All callers received None and fell through to the Groq
                         fallback unconditionally.

  Bug 6  — "medium" priority (returned by Groq) is not a valid Task.PRIORITY_CHOICES
            value (critical / high / normal / low). Normalised in both
            _structure_tasks() and _parse_response() via _normalise_priority().

  Bug 7  — AgentBuilderService.create_agent() stored role/goal/backstory only
            in metadata, not in the Resource model fields. build_crewai_agent()
            in agents/services.py reads the model fields first; blank fields
            caused CrewAI to receive empty role/goal strings.
            Fix: set resource.role, resource.goal, resource.backstory explicitly.

  Bug 15 — AgentBuilderService.create_agent() always used the dept-default
            color and ignored the color the user picked in the builder form.
            The frontend sends color inside metadata_extra, but create_agent()
            only accepted a flat kwarg list with no metadata_extra param.
            Fix: accept metadata_extra and read color from it; fall back to
            dept default if absent.

  Bug (agent assignment accuracy) — _get_available_agents() only sent
            role+goal+skills to Groq. Groq had no concrete signal about what
            each agent can actually execute, so it would assign CRM-write tasks
            to agents lacking "CRM Write" (e.g. Sales Intelligence Agent) and
            then hallucinate a nonexistent tool name like "crm_update".
            Fix: include each agent's real `tools` field in the prompt line,
            and add an explicit tool-capability constraint to the Rules section.
"""

import os
import json
import time
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import httpx
from django.conf import settings
from django.utils import timezone
from .models import Task, Goal, GoalTemplate, TaskDependency, TaskExecutionHistory
from crmapp.agentic.core.models import Resource

logger = logging.getLogger(__name__)

AGENT_TYPES = ["AI Agent", "ai_agent"]


# ═══════════════════════════════════════════════════════════════════
# PRIORITY NORMALISATION
# ═══════════════════════════════════════════════════════════════════

# Bug 6 FIX — Groq returns "medium" which is not a valid PRIORITY_CHOICES
# value. Map it (and any other unexpected string) to "normal".
_PRIORITY_MAP = {
    "critical": "critical",
    "high":     "high",
    "medium":   "normal",   # Groq's "medium" → our "normal"
    "normal":   "normal",
    "low":      "low",
}

def _normalise_priority(priority: str) -> str:
    """Return a valid Task.PRIORITY_CHOICES value for any input string."""
    return _PRIORITY_MAP.get((priority or "normal").lower(), "normal")


# ═══════════════════════════════════════════════════════════════════
# CREWAI AGENT MAP
# ═══════════════════════════════════════════════════════════════════

def get_crewai_llm():
    os.environ["GROQ_API_KEY"] = getattr(settings, "GROQ_API_KEY", "")
    return "groq/llama-3.3-70b-versatile"


def get_agent_tools(tool_names: List[str]):
    try:
        from crmapp.agentic.agents.tools import get_tools_for_agent
        return get_tools_for_agent(tool_names)
    except Exception as e:
        logger.warning(f"Could not load tools: {e}")
        return []


def build_crewai_agent(resource: Resource):
    """
    Build a CrewAI Agent from a Resource row.

    BUG FIX — missing return statement:
    ------------------------------------
    The original code built the Agent object into a local variable `agent`
    but never returned it. Every caller received None and silently fell
    through to the Groq fallback, so CrewAI was never actually used.

    BUG 7 FIX — metadata fallback for role/goal/backstory:
    -------------------------------------------------------
    Agents created via AgentBuilderService store role/goal only in metadata,
    not in Resource model fields. Three-level resolution (model field →
    metadata → safe default) matches agents/services.py build_crewai_agent().
    """
    try:
        from crewai import Agent
        os.environ["GROQ_API_KEY"] = getattr(settings, "GROQ_API_KEY", "")

        tool_names = resource.metadata.get("tools", [])
        tools      = get_agent_tools(tool_names)

        meta = resource.metadata or {}

        # Three-level resolution: model field → metadata → safe default
        role = (
            resource.role
            or meta.get("role", "")
            or resource.name
        )
        goal = (
            resource.goal
            or meta.get("goal", "")
            or f"Complete tasks assigned to {resource.name}"
        )
        backstory = (
            resource.backstory
            or meta.get("backstory", "")
            or f"You are {resource.name}, an AI agent specialized in tasks."
        )

        # Validate — CrewAI raises if these are empty
        if not role:
            role = resource.name or "AI Agent"
        if not goal:
            goal = f"Complete tasks assigned to {role}"

        agent = Agent(
            role=role,
            goal=goal,
            backstory=backstory,
            tools=tools,
            llm="groq/llama-3.3-70b-versatile",
            verbose=False,
            allow_delegation=False,
            max_iter=2,
            max_execution_time=30,
        )

        # BUG FIX: was missing — agent was built but never returned
        return agent

    except Exception as e:
        logger.error(f"Failed to build CrewAI agent for {resource.name}: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════
# GROQ GOAL PARSER SERVICE
# ═══════════════════════════════════════════════════════════════════

class GroqGoalParserService:

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or getattr(settings, "GROQ_API_KEY", None)
        if not self.api_key:
            raise ValueError("GROQ_API_KEY is required.")

        self.api_url = getattr(settings, "GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions")
        self.model   = getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile")
        self.timeout = getattr(settings, "GROQ_TIMEOUT", 30.0)
        self.client  = httpx.Client(timeout=self.timeout)

    def _get_available_agents(self) -> str:
        """
        Fetch all available agents and format them for the Groq prompt.
        Includes skills AND tools so the LLM can make accurate assignment
        decisions based on what each agent can actually execute.

        BUG FIX — agent assignment accuracy:
        Previously only role+goal+skills were sent. Groq had no way to know
        an agent's ACTUAL tool list, so it would assign CRM-write tasks to
        agents with no CRM Write tool (e.g. Sales Intelligence Agent), and
        when execution started, Groq — faced with no real tool to do the
        job — hallucinated a nonexistent tool name like "crm_update" rather
        than failing gracefully. Including each agent's real `tools` field
        gives Groq concrete signal about what's actually possible, not just
        a vague skill label.
        """
        try:
            resources = Resource.objects.filter(type__in=AGENT_TYPES)
            if not resources.exists():
                return "- No capable agents available right now."
            lines = []
            for r in resources:
                meta   = r.metadata or {}
                role   = r.role or meta.get("role", "") or r.name
                goal   = r.goal or meta.get("goal", "") or f"Complete {r.name} tasks"
                dept   = meta.get("dept", r.type)
                skills = meta.get("skills", [])
                tools  = r.tools if hasattr(r, "tools") and r.tools else meta.get("tools", [])
                skill_str = ", ".join(skills[:5]) if skills else "general"
                tools_str = ", ".join(tools) if tools else "none"
                lines.append(
                    f"- {r.name} | dept: {dept} | role: {role} | "
                    f"goal: {goal} | skills: {skill_str} | tools: {tools_str}"
                )
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Error fetching agents: {e}")
            return "- LeadFlow Agent (Sales)\n- SupportTriage Agent (Support)"


    def _build_prompt(self, goal_text: str) -> str:
        agents_list = self._get_available_agents()
        return f"""You are a task planning AI for a CRM system. Break down the following business goal into actionable tasks and assign each task to the most suitable agent.

Available Agents:
{agents_list}

Goal: {goal_text}

Each task must include:
- task_name: Clear, actionable name
- description: Brief explanation
- priority: "critical", "high", "normal", or "low"
- dependencies: List of task_names that must complete first (empty array if none)
- estimated_steps: Integer (1-10)
- assigned_agent: Name of the most suitable agent from the list above

Return ONLY valid JSON array. No preamble. Format exactly:
[
  {{
    "task_name": "Analyze current sales data",
    "description": "Review existing sales metrics and identify patterns",
    "priority": "high",
    "dependencies": [],
    "estimated_steps": 3,
    "assigned_agent": "LeadFlow Agent"
  }},
  ...
]

Rules:
- First task must have empty dependencies
- Each dependency must reference a valid task_name from previous tasks
- Assign each task to the MOST SUITABLE agent. Match task keywords to agent dept and skills:
  * Email, outreach, leads, research → Sales dept agents
  * Invoice, payment, billing, finance → Finance dept agents
  * Ticket, support, help → Support dept agents
  * Campaign, marketing → Marketing dept agents
  * CRM data, contacts, retention → CRM dept agents
- NEVER assign a Finance agent to a Sales/research task or vice versa
- CRITICAL: If a task requires writing, updating, or creating CRM records
  (leads, contacts, deals, tasks, goals), the assigned_agent's tools list
  MUST include "CRM Write". If a task only requires reading CRM data,
  the assigned_agent's tools must include "CRM Read". NEVER assign a
  CRM-write task to an agent that lacks "CRM Write" in its tools list —
  pick a different agent that has it, even if its role/dept seems less
  on-topic, since correctness of available tools matters more than
  thematic fit.
- assigned_agent MUST be the exact name of one agent from the list above
- Maximum 8 tasks per goal
"""


    def _parse_response(self, response_text: str) -> List[Dict]:
        response_text = response_text.strip()

        for prefix in ["```json", "```"]:
            if response_text.startswith(prefix):
                response_text = response_text[len(prefix):]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        response_text = response_text.strip()

        try:
            tasks = json.loads(response_text)

            if isinstance(tasks, dict):
                if "tasks" in tasks:
                    tasks = tasks["tasks"]
                elif "data" in tasks:
                    tasks = tasks["data"]
                else:
                    for value in tasks.values():
                        if isinstance(value, list):
                            tasks = value
                            break

            if not isinstance(tasks, list):
                raise ValueError("Response is not a list")

            for task in tasks:
                for field in ["task_name", "priority", "dependencies", "estimated_steps"]:
                    if field not in task:
                        task[field] = (
                            []       if field == "dependencies"   else
                            "normal" if field == "priority"       else  # Bug 6 FIX: was "medium"
                            1
                        )
                # Bug 6 FIX: normalise whatever Groq returned (may be "medium")
                task["priority"] = _normalise_priority(task["priority"])

                if "assigned_agent" not in task:
                    task["assigned_agent"] = None

            return tasks[:8]

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Groq response: {e}")
            raise ValueError(f"Invalid JSON response from Groq: {str(e)}")

    def parse_goal(self, goal_text: str, template_id: Optional[str] = None) -> Dict[str, Any]:
        start_time = time.time()

        if template_id:
            try:
                template = GoalTemplate.objects.get(id=template_id, is_active=True)
                template.usage_count += 1
                template.save()
                return {
                    "parsed_goal":     template.goal_text,
                    "tasks":           template.template_tasks,
                    "parsing_time_ms": int((time.time() - start_time) * 1000),
                    "from_template":   True,
                }
            except GoalTemplate.DoesNotExist:
                logger.warning(f"Template {template_id} not found, falling back to Groq")

        try:
            logger.info(f"Calling Groq API for goal: {goal_text[:50]}...")

            response = self.client.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type":  "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "You are a task planning AI that outputs only valid JSON."},
                        {"role": "user",   "content": self._build_prompt(goal_text)},
                    ],
                    "temperature": getattr(settings, "GROQ_TEMPERATURE", 0.3),
                    "max_tokens":  getattr(settings, "GROQ_MAX_TOKENS", 2000),
                },
            )
            response.raise_for_status()
            data    = response.json()
            content = data["choices"][0]["message"]["content"]
            tasks   = self._parse_response(content)
            parsing_time = int((time.time() - start_time) * 1000)

            logger.info(f"Groq API returned {len(tasks)} tasks in {parsing_time}ms")

            return {
                "parsed_goal":     goal_text,
                "tasks":           tasks,
                "parsing_time_ms": parsing_time,
                "from_template":   False,
                "llm_response":    data,
            }

        except httpx.HTTPError as e:
            logger.error(f"Groq API HTTP error: {e}")
            raise ValueError(f"Groq API error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in goal parsing: {e}")
            raise


# ═══════════════════════════════════════════════════════════════════
# TASK PLANNING SERVICE
# ═══════════════════════════════════════════════════════════════════

class TaskPlanningService:

    def __init__(self):
        self.groq_service = GroqGoalParserService()

    def create_goal_from_input(
        self,
        goal_text: str,
        user=None,
        template_id: Optional[str] = None,
    ) -> Goal:

        goal = Goal.objects.create(
            user_input=goal_text,
            status="parsing",
            created_by=user,
        )

        try:
            parse_result = self.groq_service.parse_goal(goal_text, template_id)

            goal.parsed_goal     = parse_result["parsed_goal"]
            goal.parsing_time_ms = parse_result["parsing_time_ms"]
            goal.status          = "parsed"

            if not parse_result.get("from_template"):
                goal.llm_response = parse_result.get("llm_response", {})

            structured_tasks      = self._structure_tasks(parse_result["tasks"])
            goal.structured_tasks = structured_tasks
            goal.status           = "building"
            goal.save()

            self._create_tasks_from_structure(goal, structured_tasks, user)

            goal.status = "ready"
            goal.save()

            return goal

        except Exception as e:
            goal.status        = "failed"
            goal.error_message = str(e)
            goal.save()
            raise

    def _structure_tasks(self, raw_tasks: List[Dict]) -> List[Dict]:
        structured = []

        for i, task in enumerate(raw_tasks):
            # Bug 6 FIX: normalise priority before storing in structured_tasks
            # so "medium" never reaches Task.priority or the frontend badge logic
            priority = _normalise_priority(task.get("priority", "normal"))

            structured_task = {
                "task_name":          task.get("task_name", f"Task {i+1}"),
                "description":        task.get("description", ""),
                "priority":           priority,
                "dependencies":       task.get("dependencies", []),
                "estimated_steps":    task.get("estimated_steps", 1),
                "status":             "blocked" if task.get("dependencies") else "ready",
                "task_id":            f"tsk-auto-{i+1:03d}",
                "assigned_agent":     task.get("assigned_agent", None),
                "created_at":         timezone.now().isoformat(),
                "updated_at":         timezone.now().isoformat(),
                "actual_duration_ms": None,
            }
            structured.append(structured_task)

        return structured

    def _create_tasks_from_structure(
        self,
        goal: Goal,
        structured_tasks: List[Dict],
        user=None,
    ) -> List[Task]:
        created_tasks = []
        task_map      = {}

        for task_data in structured_tasks:
            assigned_agent = task_data.get("assigned_agent")

            task = Task.objects.create(
                name            = task_data["task_name"],
                description     = task_data.get("description", ""),
                priority        = task_data["priority"],   # already normalised
                status          = task_data["status"],
                dept            = self._infer_department(task_data["task_name"], assigned_agent),
                assignee        = assigned_agent,
                estimated_steps = task_data["estimated_steps"],
                created_by      = user,
                metadata        = {
                    "goal_id": str(goal.id),
                    "source":  "goal_parser",
                    "assigned_agent": assigned_agent,
                },
            )

            task_map[task_data["task_name"]] = task
            created_tasks.append(task)

        # Wire up depends_on FK and TaskDependency records
        for task_data in structured_tasks:
            if task_data["dependencies"]:
                task = task_map[task_data["task_name"]]
                for dep_name in task_data["dependencies"]:
                    if dep_name in task_map:
                        dep_task        = task_map[dep_name]
                        task.depends_on = dep_task
                        task.save(update_fields=["depends_on"])

                        TaskDependency.objects.get_or_create(
                            from_task = dep_task,
                            to_task   = task,
                            defaults  = {
                                "dependency_type": "sequential",
                                "label": f"Generated from goal {goal.id}",
                            },
                        )

        return created_tasks

    def _infer_department(self, task_name: str, assigned_agent: str = None) -> str:
        if assigned_agent:
            agent_lower = assigned_agent.lower()
            if any(w in agent_lower for w in ["lead", "sales"]):
                return "Sales"
            elif any(w in agent_lower for w in ["support", "triage"]):
                return "Support"
            elif any(w in agent_lower for w in ["invoice", "finance", "recovery"]):
                return "Finance"
            elif any(w in agent_lower for w in ["marketing", "orchestrator"]):
                return "Marketing"
            elif any(w in agent_lower for w in ["churn", "crm", "guard"]):
                return "CRM"
            elif any(w in agent_lower for w in ["hr", "onboarding"]):
                return "HR"
            elif any(w in agent_lower for w in ["analytics", "engine"]):
                return "Analytics"

        task_lower = task_name.lower()
        if any(w in task_lower for w in ["sale", "lead", "customer", "email", "outreach"]):
            return "Sales"
        elif any(w in task_lower for w in ["invoice", "payment", "finance", "billing"]):
            return "Finance"
        elif any(w in task_lower for w in ["support", "ticket", "help"]):
            return "Support"
        elif any(w in task_lower for w in ["market", "campaign", "ad"]):
            return "Marketing"
        elif any(w in task_lower for w in ["analytics", "report", "data"]):
            return "Analytics"
        elif any(w in task_lower for w in ["hr", "employee", "onboarding"]):
            return "HR"
        else:
            return "CRM"

    def execute_task_with_crewai(self, task_id: str) -> Dict[str, Any]:
        try:
            from crewai import Task as CrewTask, Crew

            task = Task.objects.get(id=task_id)

            if task.status not in ("ready", "running"):
                return {
                    "success":        False,
                    "error":          f"Task not ready (status: {task.status})",
                    "failure_reason": f"Task status was '{task.status}', expected 'ready'",
                }

            task.status = "running"
            task.save(update_fields=["status"])

            history = TaskExecutionHistory.objects.create(
                task       = task,
                status     = "success",
                started_at = timezone.now(),
                agent      = task.assignee or "AI Agent",
                dept       = task.dept,
            )

            start_time = time.time()

            crewai_agent   = None
            agent_resource = None

            if task.assignee:
                agent_resource = Resource.objects.filter(
                    name__icontains=task.assignee,
                    type__in=AGENT_TYPES,
                ).first()
                if agent_resource:
                    crewai_agent = build_crewai_agent(agent_resource)
                else:
                    logger.warning(
                        f"[TaskService] No resource found for assignee='{task.assignee}' "
                        f"— falling back to Groq direct"
                    )

            result_output  = ""
            failure_reason = None

            if crewai_agent:
                try:
                    crew_task = CrewTask(
                        description     = f"{task.name}\n\n{task.description or ''}",
                        expected_output = f"Complete result of: {task.name}",
                        agent           = crewai_agent,
                    )
                    crew   = Crew(agents=[crewai_agent], tasks=[crew_task], verbose=False)
                    result = crew.kickoff()
                    result_output = str(result)
                    logger.info(f"[TaskService] CrewAI done for {task_id}: {result_output[:100]}")

                except Exception as crew_error:
                    logger.error(f"[TaskService] CrewAI error: {crew_error} — trying Groq fallback")
                    failure_reason = f"CrewAI failed ({crew_error}), used Groq fallback"
                    result_output  = self._execute_with_groq(task)
            else:
                failure_reason = (
                    f"No CrewAI agent built for '{task.assignee or 'unassigned'}' — used Groq fallback"
                )
                result_output = self._execute_with_groq(task)

            duration_ms = int((time.time() - start_time) * 1000)

            task.status             = "completed"
            task.progress           = 100
            task.actual_duration_ms = duration_ms
            task.last_run           = timezone.now()
            task.metadata["last_result"] = result_output[:500]
            if failure_reason:
                task.metadata["fallback_note"] = failure_reason
            else:
                task.metadata.pop("failure_reason", None)
            task.save()

            history.status       = "success"
            history.completed_at = timezone.now()
            history.duration_ms  = duration_ms
            history.metadata     = {"result": result_output[:500]}
            history.save()

            self._unblock_dependent_tasks(task)

            return {
                "success":     True,
                "task_id":     task.id,
                "task_name":   task.name,
                "agent":       task.assignee,
                "duration_ms": duration_ms,
                "result":      result_output[:300],
            }

        except Task.DoesNotExist:
            return {"success": False, "error": "Task not found"}

        except Exception as e:
            logger.error(f"[TaskService] Error executing task {task_id}: {e}")
            failure_reason = str(e)
            try:
                task = Task.objects.get(id=task_id)
                task.status = "failed"
                task.metadata["failure_reason"] = failure_reason
                task.save(update_fields=["status", "metadata"])

                history = TaskExecutionHistory.objects.filter(
                    task=task
                ).order_by("-started_at").first()
                if history:
                    history.status        = "failed"
                    history.completed_at  = timezone.now()
                    history.error_details = {"error": failure_reason}
                    history.save()
            except Exception:
                pass
            return {"success": False, "error": failure_reason}

    def _execute_with_groq(self, task: Task) -> str:
        try:
            groq_service = GroqGoalParserService()
            response = groq_service.client.post(
                groq_service.api_url,
                headers={
                    "Authorization": f"Bearer {groq_service.api_key}",
                    "Content-Type":  "application/json",
                },
                json={
                    "model": groq_service.model,
                    "messages": [
                        {
                            "role":    "system",
                            "content": (
                                f"You are {task.assignee or 'an AI agent'}. "
                                f"Complete the given task and provide a detailed result."
                            ),
                        },
                        {
                            "role":    "user",
                            "content": (
                                f"Task: {task.name}\n\n"
                                f"Description: {task.description or task.name}\n\n"
                                f"Provide a detailed completion report."
                            ),
                        },
                    ],
                    "temperature": 0.3,
                    "max_tokens":  500,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"[TaskService] Groq fallback failed: {e}")
            return (
                f"Task '{task.name}' processed by {task.assignee or 'AI Agent'} "
                f"(Groq unavailable: {e})"
            )

    def execute_task(self, task_id: str) -> Dict[str, Any]:
        return self.execute_task_with_crewai(task_id)

    def execute_goal_tasks(self, goal_id: str) -> Dict[str, Any]:
        try:
            goal  = Goal.objects.get(id=goal_id)
            tasks = Task.objects.filter(
                metadata__goal_id=str(goal_id)
            ).order_by("created_at")

            if not tasks.exists():
                return {"success": False, "error": "No tasks found for this goal"}

            goal.status = "executing"
            goal.save(update_fields=["status"])

            results        = []
            max_iterations = tasks.count() * 2
            iteration      = 0

            while iteration < max_iterations:
                iteration += 1

                tasks = Task.objects.filter(metadata__goal_id=str(goal_id))
                ready_task = tasks.filter(status="ready").first()

                if not ready_task:
                    remaining = tasks.exclude(status__in=["completed", "failed"])
                    if not remaining.exists():
                        break

                    unblocked = False
                    for t in remaining.filter(status="blocked"):
                        dep = t.depends_on
                        if dep:
                            dep = Task.objects.filter(id=dep.id).first()
                            if dep and dep.status == "completed":
                                t.status = "ready"
                                t.metadata.pop("failure_reason", None)
                                t.save(update_fields=["status", "metadata"])
                                unblocked = True
                    if not unblocked:
                        break
                    continue

                result = self.execute_task_with_crewai(ready_task.id)
                results.append(result)

            tasks           = Task.objects.filter(metadata__goal_id=str(goal_id))
            completed_count = tasks.filter(status="completed").count()
            total_count     = tasks.count()

            goal.status = "completed" if completed_count > 0 else "failed"
            goal.metadata["progress"] = (
                int((completed_count / total_count) * 100) if total_count > 0 else 0
            )
            goal.save()

            return {
                "success":     completed_count > 0,
                "goal_id":     goal_id,
                "total_tasks": total_count,
                "completed":   completed_count,
                "progress":    goal.metadata["progress"],
                "results":     results,
            }

        except Goal.DoesNotExist:
            return {"success": False, "error": "Goal not found"}
        except Exception as e:
            logger.error(f"[TaskService] Error executing goal {goal_id}: {e}")
            return {"success": False, "error": str(e)}

    def get_ready_tasks(self) -> List[Task]:
        return Task.objects.filter(status="ready").order_by("-priority", "created_at")

    def _unblock_dependent_tasks(self, completed_task: Task):
        """Unblock tasks that were waiting on this completed task."""
        dependent_tasks = Task.objects.filter(depends_on=completed_task)

        for task in dependent_tasks:
            if task.status not in ("completed", "failed", "running"):
                dep = task.depends_on
                if dep:
                    fresh_dep = Task.objects.filter(id=dep.id).first()
                    if fresh_dep and fresh_dep.status == "completed":
                        task.status = "ready"
                        task.metadata.pop("failure_reason", None)
                        task.save(update_fields=["status", "metadata"])
                        logger.info(f"[TaskService] Unblocked task: {task.name}")


# ═══════════════════════════════════════════════════════════════════
# AGENT BUILDER SERVICE
# ═══════════════════════════════════════════════════════════════════

class AgentBuilderService:
    """
    Creates Resource rows from the tasks-app agent builder form.

    BUG 7 FIX — set resource.role, resource.goal, resource.backstory as model
    fields (not just in metadata). build_crewai_agent() in agents/services.py
    reads model fields first; blank fields caused CrewAI to receive empty
    role/goal strings even though the values existed in metadata.

    BUG 15 FIX — accept metadata_extra kwarg so the color the user picked in
    the builder form is actually used. Previously only the dept-default color
    was applied regardless of the user's choice.
    """

    def create_agent(
        self,
        name: str,
        role: str,
        goal: str,
        backstory: str,
        tools: List[str],
        dept: str = "CRM",
        user=None,
        metadata_extra: Dict = None,   # Bug 15 FIX: accept form's metadata_extra
    ) -> Resource:

        if Resource.objects.filter(name=name).exists():
            raise ValueError(f"Agent '{name}' already exists")

        extra = metadata_extra or {}

        # Bug 15 FIX: use color from metadata_extra if provided, else dept default
        color = extra.get("color") or self._get_color(dept)

        resource = Resource.objects.create(
            name            = name,
            type            = "AI Agent",
            status          = "idle",
            load_percentage = 0,
            # Bug 7 FIX: set model fields explicitly so build_crewai_agent()
            # finds them at level 1 without needing the metadata fallback
            role            = role,
            goal            = goal,
            backstory       = backstory,
            color           = color,           # Bug 15 FIX
            metadata        = {
                "role":       role,
                "goal":       goal,
                "backstory":  backstory,
                "tools":      tools,
                "dept":       dept,
                "is_custom":  True,
                "color":      color,
                "created_by": str(user) if user else None,
                # Merge any extra fields the frontend sent
                **{k: v for k, v in extra.items() if k not in ("color",)},
            },
        )

        logger.info(
            f"[AgentBuilder] Created custom agent: {name} "
            f"(role='{role[:40]}', dept={dept}, color={color})"
        )
        return resource

    def test_agent(self, resource_id: str, test_prompt: str) -> Dict[str, Any]:
        try:
            resource = Resource.objects.get(id=resource_id)
            agent    = build_crewai_agent(resource)

            if not agent:
                return {"success": False, "error": "Could not build CrewAI agent"}

            from crewai import Task as CrewTask, Crew

            test_task = CrewTask(
                description     = test_prompt,
                expected_output = "Detailed response to the test prompt",
                agent           = agent,
            )
            crew   = Crew(agents=[agent], tasks=[test_task], verbose=False)
            result = crew.kickoff()

            return {"success": True, "agent": resource.name, "result": str(result)[:500]}

        except Exception as e:
            logger.error(f"[AgentBuilder] Agent test failed: {e}")
            return {"success": False, "error": str(e)}

    def _get_color(self, dept: str) -> str:
        return {
            "Sales":     "#3a9aab",
            "Support":   "#f97316",
            "Finance":   "#4ade80",
            "Marketing": "#fbbf24",
            "CRM":       "#a78bfa",
            "HR":        "#f87171",
            "Analytics": "#3a9aab",
        }.get(dept, "#3a9aab")
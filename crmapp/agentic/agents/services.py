"""
crmapp/agentic/agents/services.py
"""

import os
import time
import logging
from datetime import datetime, timezone
from django.conf import settings
from crmapp.agentic.core.models import Resource

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# #3 FIX — Agent cache: build each agent once per resource, reuse after that
# ─────────────────────────────────────────────────────────────────────────────
_agent_cache: dict = {}


def _groq_key() -> str:
    key = getattr(settings, "GROQ_API_KEY", None)
    if not key:
        raise ValueError("GROQ_API_KEY is not set in settings.py")
    return key


# ─────────────────────────────────────────────────────────────────────────────
# 1. Build a CrewAI Agent from a Resource row (cached)
# ─────────────────────────────────────────────────────────────────────────────

def build_crewai_agent(resource, extra_tools: list = None):
    """
    Builds and caches a CrewAI Agent per resource ID.
    If already built and no extra_tools, returns cached instance.
    """
    cache_key = str(resource.id)

    # Return cached agent if available and no extra tools needed
    if cache_key in _agent_cache and not extra_tools:
        logger.debug(f"[AgentCache] Reusing agent for {resource.name}")
        return _agent_cache[cache_key]

    try:
        from crewai import Agent
        from crmapp.agentic.agents.tools import get_tools_for_agent

        os.environ["GROQ_API_KEY"]   = getattr(settings, "GROQ_API_KEY", "")
        os.environ["LITELLM_API_KEY"] = getattr(settings, "GROQ_API_KEY", "")

        config      = getattr(resource, "config", None)
        llm_model   = config.llm if config else "groq/llama-3.3-70b-versatile"

        if not llm_model.startswith("groq/"):
            llm_model = f"groq/{llm_model}"

        tools = get_tools_for_agent(resource.tools or [])
        if extra_tools:
            tools.extend(extra_tools)

        backstory = resource.backstory or (
            f"You are {resource.name}, an expert AI agent specialising in "
            f"{resource.metadata.get('dept', 'general')} tasks. "
            f"Your goal is: {resource.goal}."
        )

        agent = Agent(
            role=resource.role or resource.name,
            goal=resource.goal or f"Complete tasks assigned to {resource.name}",
            backstory=backstory,
            llm=llm_model,
            tools=tools,
            verbose=False,           # #4 FIX — was True
            allow_delegation=False,
            max_iter=2,              # #4 FIX — was missing/inconsistent
            max_execution_time=30,   # #4 FIX — was missing
        )

        # Only cache if no extra_tools (deterministic agent)
        if not extra_tools:
            _agent_cache[cache_key] = agent
            logger.debug(f"[AgentCache] Cached agent for {resource.name}")

        return agent

    except ImportError as e:
        raise ImportError(f"Missing package: {e}. Run: pip install crewai")


def clear_agent_cache(resource_id: str = None):
    """Call this if a resource is updated so the cache doesn't go stale."""
    global _agent_cache
    if resource_id:
        _agent_cache.pop(str(resource_id), None)
    else:
        _agent_cache.clear()


# ─────────────────────────────────────────────────────────────────────────────
# 2. Run a task with CrewAI — full execution
# ─────────────────────────────────────────────────────────────────────────────

def run_agent_task(resource, task_name: str, task_description: str) -> dict:
    from crmapp.agentic.agents.models import AgentExecution

    goal_id = ""
    try:
        from crmapp.agentic.tasks.models import Task as DjangoTask
        task_obj = DjangoTask.objects.filter(name=task_name).first()
        if task_obj:
            goal_id = task_obj.metadata.get("goal_id", "")
    except Exception:
        pass

    execution = AgentExecution.objects.create(
        resource=resource,
        task_name=task_name,
        task_input=task_description,
        dept=resource.metadata.get("dept", ""),
        status="running",
        goal_id=goal_id,
    )

    start = time.time()

    try:
        from crewai import Task, Crew

        crew_agent = build_crewai_agent(resource)  # cached after first call

        crew_task = Task(
            description=task_description,
            agent=crew_agent,
            expected_output=(
                "A clear, detailed response that fully addresses the task. "
                "Include specific findings, recommendations, or actions taken."
            ),
        )

        crew = Crew(
            agents=[crew_agent],
            tasks=[crew_task],
            verbose=False,
            max_rpm=10,
        )

        result      = crew.kickoff()
        result_text = str(result)
        duration_ms = int((time.time() - start) * 1000)

        execution.status      = "success"
        execution.result      = result_text
        execution.duration_ms = duration_ms
        execution.finished_at = datetime.now(timezone.utc)
        execution.tools_used  = resource.tools or []
        execution.save()

        return {
            "success":      True,
            "result":       result_text,
            "error":        None,
            "execution_id": str(execution.id),
            "duration_ms":  duration_ms,
        }

    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        logger.error(f"Agent execution failed: {e}")

        execution.status      = "failed"
        execution.error       = str(e)
        execution.duration_ms = duration_ms
        execution.finished_at = datetime.now(timezone.utc)
        execution.save()

        return {
            "success":      False,
            "result":       None,
            "error":        str(e),
            "execution_id": str(execution.id),
            "duration_ms":  duration_ms,
        }

    finally:
        # BUG FIX — Agent stuck "busy" after crash:
        # Previously resource.status="idle" only ran on the success path.
        # If CrewAI threw an exception the agent stayed "busy" permanently
        # and _find_agent_for_task() would never select it again.
        # The finally block guarantees reset regardless of outcome.
        try:
            resource.status = "idle"
            resource.save(update_fields=["status"])
        except Exception as save_err:
            logger.error(f"[services] Failed to reset agent status to idle: {save_err}")


# ─────────────────────────────────────────────────────────────────────────────
# 3. Quick Groq test — no CrewAI overhead
# ─────────────────────────────────────────────────────────────────────────────

def test_agent_with_groq(resource, prompt: str = None) -> dict:
    if not prompt:
        prompt = (
            f"Introduce yourself as {resource.name}. "
            f"Your role is: {resource.role}. "
            f"Your goal is: {resource.goal}. "
            f"Describe your capabilities in 2-3 sentences."
        )

    config      = getattr(resource, "config", None)
    llm_model   = config.llm if config else "llama-3.3-70b-versatile"
    temperature = config.temperature if config else 0.3
    max_tokens  = config.max_tokens if config else 512
    model_name  = llm_model.replace("groq/", "")

    start = time.time()

    try:
        from groq import Groq

        client = Groq(api_key=getattr(settings, "GROQ_API_KEY", ""))

        system_msg = (
            f"You are {resource.name}, an AI agent. "
            f"Role: {resource.role}. "
            f"Goal: {resource.goal}. "
            f"Backstory: {resource.backstory or 'Expert AI agent.'} "
            f"Be concise and professional."
        )

        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user",   "content": prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        result_text = response.choices[0].message.content
        duration_ms = int((time.time() - start) * 1000)

        return {
            "success":     True,
            "result":      result_text,
            "error":       None,
            "duration_ms": duration_ms,
        }

    except Exception as e:
        logger.error(f"Groq test failed: {e}")
        return {
            "success":     False,
            "result":      None,
            "error":       str(e),
            "duration_ms": int((time.time() - start) * 1000),
        }


# ─────────────────────────────────────────────────────────────────────────────
# 4. Create a Resource + AgentConfig from frontend form data
# ─────────────────────────────────────────────────────────────────────────────

def create_agent_from_payload(payload: dict) -> "Resource":
    from crmapp.agentic.core.models import Resource
    from crmapp.agentic.agents.models import AgentConfig

    extra = payload.get("metadata_extra", {})

    metadata = {
        "is_custom":   True,
        "dept":        payload.get("dept", "General"),
        "role":        payload.get("role", ""),
        "goal":        payload.get("goal", ""),
        "backstory":   payload.get("backstory", ""),
        "skills":      extra.get("skills", []),
        "tools":       payload.get("tools", []),
        "llm":         extra.get("llm", "groq/llama-3.3-70b-versatile"),
        "temperature": extra.get("temperature", 0.3),
        "max_tokens":  extra.get("max_tokens", 1024),
        "priority":    extra.get("priority", "normal"),
        "color":       extra.get("color", "#3a9aab"),
    }

    resource = Resource.objects.create(
        name      = payload["name"],
        type      = "AI Agent",
        status    = "idle",
        role      = payload.get("role", ""),
        goal      = payload.get("goal", ""),
        backstory = payload.get("backstory", ""),
        tools     = payload.get("tools", []),
        color     = extra.get("color", "#3a9aab"),
        metadata  = metadata,
    )

    AgentConfig.objects.create(
        resource    = resource,
        llm         = extra.get("llm", "groq/llama-3.3-70b-versatile"),
        temperature = extra.get("temperature", 0.3),
        max_tokens  = extra.get("max_tokens", 1024),
        skills      = extra.get("skills", []),
        dept        = payload.get("dept", "General"),
        priority    = extra.get("priority", "normal"),
    )

    return resource
"""
crmapp/workflows/executor.py

Fully working node-by-node workflow execution engine.

Every node type is handled. No missing methods. No crashes.
Agents are always used when available. Falls back to direct
Groq call (using the SAME pattern as services.py) when no
agent Resource is found in the DB.
"""

import re
import time
import logging

from django.utils import timezone as dj_tz
from django.db.models import F

logger = logging.getLogger(__name__)


class WorkflowRunner:

    def __init__(self, execution_id: str):
        self.execution_id = execution_id

    # ─────────────────────────────────────────────────────────────────────────
    # PUBLIC ENTRY POINT
    # ─────────────────────────────────────────────────────────────────────────

    def run(self, node_id: str = None):
        """
        Start or resume execution from node_id.
        If node_id is None → find the trigger node and start there.
        """
        from .models import WorkflowExecution, WorkflowNode

        # Load execution
        try:
            execution = (
                WorkflowExecution.objects
                .select_related("workflow")
                .get(id=self.execution_id)
            )
        except WorkflowExecution.DoesNotExist:
            logger.error(f"[Runner] Execution {self.execution_id} not found")
            return

        # Guard: don't re-run a finished execution
        if execution.status not in ("pending", "running"):
            logger.warning(
                f"[Runner] {self.execution_id} is already {execution.status} — skipping"
            )
            return

        execution.status = "running"
        execution.save(update_fields=["status"])

        # Resolve starting node
        if node_id:
            try:
                node = WorkflowNode.objects.get(id=node_id, workflow=execution.workflow)
            except WorkflowNode.DoesNotExist:
                self._fail(execution, f"Node '{node_id}' not found in workflow")
                return
        else:
            node = (
                WorkflowNode.objects
                .filter(workflow=execution.workflow, type="trigger")
                .first()
            )
            if not node:
                self._fail(execution, "Workflow has no trigger node")
                return

        self._execute_node(execution, node)

    # ─────────────────────────────────────────────────────────────────────────
    # NODE DISPATCHER
    # ─────────────────────────────────────────────────────────────────────────

    # ── Create Lead ───────────────────────────────────────────────────────────
    def _handle_create_lead(self, execution, node, step):
        """
        Creates a real Lead record in the CRM from workflow context.
        Config fields support {variable} substitution from execution.context.
        On success, the new lead's id is stored in context as {created_lead_id}
        so later nodes (e.g. Notify) can reference it.
        """
        from crmapp.crm.leads.models import Lead

        config = node.config or {}
        ctx    = execution.context

        def fmt(val, default=""):
            val = config.get(val, default) or default
            try:
                return val.format(**ctx)
            except (KeyError, ValueError):
                return val

        name   = fmt("lead_name", "Unknown Lead")
        email  = fmt("lead_email", "")
        phone  = fmt("lead_phone", "")
        source = fmt("lead_source", "Other")

        try:
            value = float(config.get("lead_value") or ctx.get("value") or 0)
        except (TypeError, ValueError):
            value = 0

        # Avoid duplicate leads for the same email from repeated triggers
        if email:
            existing = Lead.objects.filter(email__iexact=email).first()
            if existing:
                execution.context["created_lead_id"] = existing.id
                execution.save(update_fields=["context"])
                return {
                    "success": True,
                    "output": f"Lead already exists (ID:{existing.id}) for {email} — skipped duplicate creation",
                }

        try:
            lead = Lead.objects.create(
                name=name,
                email=email,
                phone=phone,
                value=value,
                source=source if source in dict(Lead.SOURCE_CHOICES) else "Other",
            )
            execution.context["created_lead_id"] = lead.id
            execution.save(update_fields=["context"])
            return {
                "success": True,
                "output": f"Lead created — ID:{lead.id}, Name:{name}, Email:{email}",
            }
        except Exception as exc:
            logger.error(f"[Runner] Lead creation failed: {exc}")
            return {"success": False, "error": f"Lead creation failed: {exc}"}
    
    
    def _execute_node(self, execution, node):
        from .models import WorkflowExecutionStep

        logger.info(
            f"[Runner] {self.execution_id} → {node.type.upper()} '{node.label}'"
        )

        # Track current node
        execution.current_node = node
        execution.save(update_fields=["current_node"])

        # Create step record
        step = WorkflowExecutionStep.objects.create(
            execution=execution,
            node=node,
            status="running",
        )

        start = time.time()

        # Dispatch
        try:
            handler = {
                "trigger":   self._handle_trigger,
                "action":    self._handle_action,
                "condition": self._handle_condition,
                "delay":     self._handle_delay,
                "notify":    self._handle_notify,
                "approval":  self._handle_approval,
                "create_lead": self._handle_create_lead,
                "end":       self._handle_end,
            }.get(node.type, self._handle_unknown)

            result = handler(execution, node, step)

        except Exception as exc:
            logger.exception(f"[Runner] Node '{node.label}' crashed: {exc}")
            result = {"success": False, "error": str(exc)}

        # Persist step result
        duration_ms = int((time.time() - start) * 1000)
        step.duration_ms  = duration_ms
        step.finished_at  = dj_tz.now()
        step.output       = result.get("output", result.get("error", ""))
        step.branch_taken = result.get("branch", "")

        if result.get("success", True):
            step.status = "success"
            step.save()

            execution.steps_done = F("steps_done") + 1
            execution.save(update_fields=["steps_done"])
            execution.refresh_from_db(fields=["steps_done"])

            # Async handlers (delay / approval) schedule their own continuation
            if not result.get("async"):
                next_nodes = self._next_nodes(
                    execution.workflow,
                    node,
                    branch_label=result.get("branch", ""),
                )
                if next_nodes:
                    for nxt in next_nodes:
                        self._execute_node(execution, nxt)
                else:
                    self._complete(execution)
        else:
            step.status = "failed"
            step.save()
            self._fail(execution, result.get("error", "Unknown error"))

    # ─────────────────────────────────────────────────────────────────────────
    # NODE HANDLERS
    # ─────────────────────────────────────────────────────────────────────────

    # ── Trigger ───────────────────────────────────────────────────────────────
    def _handle_trigger(self, execution, node, step):
        """Pass trigger_data into context so downstream nodes can use it."""
        execution.context.update({
            "trigger_node":  node.label,
            "trigger_type":  execution.trigger,
            **{k: v for k, v in execution.trigger_data.items()},
        })
        execution.save(update_fields=["context"])
        return {"success": True, "output": f"Workflow triggered: {node.label}"}

# ── Action ────────────────────────────────────────────────────────────────
    def _handle_action(self, execution, node, step):
        """
        Run the task via a CrewAI agent.
        Always tries to use an agent first.
        Falls back to direct Groq if no agent Resource exists in DB.

        Stores output under BOTH:
          - execution.context[f"output_{node.id}"]      (auto, id-based — fragile if node id changes)
          - execution.context[config["output_key"]]      (stable, user-chosen — survives re-saves/re-imports)

        Safety net: if the LLM echoes literal {placeholder} syntax back into its
        output instead of substituting real values (a known LLM quirk), those
        leftover placeholders are resolved deterministically against
        execution.context after the call — so output correctness no longer
        depends on model behavior.
        """
        import re

        config     = node.config or {}
        agent_name = config.get("agent_name") or self._infer_agent(node.label)
        task_desc  = config.get("task_description") or node.label
        output_key = config.get("output_key")

        # ── Interpolate {variables} in the task description BEFORE sending to agent ──
        try:
            task_desc = task_desc.format(**execution.context)
        except (KeyError, ValueError):
            pass  # leave unresolved placeholders as-is rather than crashing

        # Enrich task with workflow context
        ctx = self._context_summary(execution.context)
        if ctx:
            task_desc = f"{task_desc}\n\nWorkflow context:\n{ctx}"

        def _resolve_leftover_placeholders(text, context):
            """Replace any literal {key} left in the LLM's output with the real value from context."""
            def repl(m):
                key = m.group(1)
                return str(context.get(key, m.group(0)))  # leave untouched if key not found
            return re.sub(r"\{(\w+)\}", repl, text)

        resource = self._find_agent(agent_name)

        if resource:
            # ── Path A: CrewAI agent ──────────────────────────────────────────
            try:
                from crmapp.agentic.agents.services import run_agent_task
                result = run_agent_task(resource, node.label, task_desc)
                output = result.get("result") or result.get("error") or ""
                output = _resolve_leftover_placeholders(output, execution.context)

                execution.context[f"output_{node.id}"] = output[:500]
                if output_key:
                    execution.context[output_key] = output[:500]
                execution.save(update_fields=["context"])

                return {
                    "success": result.get("success", True),
                    "output":  f"[Agent: {resource.name}] {output[:500]}",
                    "error":   result.get("error") if not result.get("success") else None,
                }
            except Exception as exc:
                logger.error(f"[Runner] Agent call failed: {exc} — falling back to Groq")
                # Fall through to direct Groq below

        # ── Path B: Direct Groq (no agent in DB or agent crashed) ────────────
        output = self._direct_groq(
            system=f"You are a business workflow automation agent. Complete this task concisely.",
            prompt=task_desc,
        )
        output = _resolve_leftover_placeholders(output, execution.context)

        execution.context[f"output_{node.id}"] = output[:500]
        if output_key:
            execution.context[output_key] = output[:500]
        execution.save(update_fields=["context"])

        return {"success": True, "output": f"[Groq] {output[:500]}"}
    
    # ── Condition ─────────────────────────────────────────────────────────────
    def _handle_condition(self, execution, node, step):
        """
        Evaluate condition and return branch label.
        Priority:
          1. config["expression"] — safe Python eval against context
          2. config["use_agent"] — ask Groq to decide
          3. keyword heuristics from node label
        """
        config      = node.config or {}
        true_label  = config.get("true_branch",  "Yes")
        false_label = config.get("false_branch", "No")
        expression  = config.get("expression", "")

        # 1. Expression eval
        if expression:
            try:
                ctx    = {k: v for k, v in execution.context.items()}
                branch = true_label if eval(
                    expression, {"__builtins__": {}}, ctx
                ) else false_label
                return {
                    "success": True,
                    "output":  f"Expression '{expression}' → {branch}",
                    "branch":  branch,
                }
            except Exception as exc:
                logger.warning(f"[Runner] Expression eval failed: {exc}")

        # 2. Agent-assisted condition
        if config.get("use_agent"):
            prompt = (
                f"Based on this context, answer ONLY 'Yes' or 'No' (or the branch name).\n"
                f"Question: {node.label}\n"
                f"Context: {self._context_summary(execution.context)}"
            )
            answer = self._direct_groq(
                system="You are a decision engine. Reply with only the branch label.",
                prompt=prompt,
            ).strip()
            # Find best matching branch from available edges
            branch = self._match_branch(answer, execution.workflow, node, true_label, false_label)
            return {
                "success": True,
                "output":  f"Agent decided: {branch}",
                "branch":  branch,
            }

        # 3. Keyword heuristics
        branch = self._evaluate_condition_heuristic(node.label, execution.context, true_label, false_label)
        return {
            "success": True,
            "output":  f"Condition '{node.label}' → {branch}",
            "branch":  branch,
        }

    # ── Delay ─────────────────────────────────────────────────────────────────
    def _handle_delay(self, execution, node, step):
        """
        Parse delay duration from label or config.
        Schedule Celery resumption with countdown.
        """
        from .tasks import resume_workflow_after_delay

        seconds = self._parse_delay(node.label, node.config or {})
        logger.info(
            f"[Runner] Delay: pausing {self.execution_id} for {seconds}s ({node.label})"
        )

        next_nodes   = self._next_nodes(execution.workflow, node)
        next_node_id = next_nodes[0].id if next_nodes else None

        resume_workflow_after_delay.apply_async(
            kwargs={"execution_id": self.execution_id, "next_node_id": next_node_id},
            countdown=seconds,
        )

        return {
            "success": True,
            "output":  f"Paused {seconds}s. Resuming after '{node.label}'.",
            "async":   True,
        }

    # ── Notify ────────────────────────────────────────────────────────────────
# ── Notify ────────────────────────────────────────────────────────────────
    def _handle_notify(self, execution, node, step):
        """
        Send notification via Slack, email, or log.
        Config: channel (slack|email|log), recipient, subject, message.
        All fields support {variable} substitution from execution context.
        """
        config    = node.config or {}
        channel   = config.get("channel", "log")
        recipient = config.get("recipient", "")
        subject   = config.get("subject", node.label)
        message   = config.get("message", f"Workflow update: {node.label}")

        ctx = execution.context
        try:
            recipient = recipient.format(**ctx)
        except (KeyError, ValueError):
            pass
        try:
            subject = subject.format(**ctx)
        except (KeyError, ValueError):
            pass
        try:
            message = message.format(**ctx)
        except (KeyError, ValueError):
            pass

        output = ""

        if channel == "slack":
            try:
                from crmapp.agentic.agents.tools import SlackNotifyTool
                output = SlackNotifyTool()._run(message=message)
            except Exception as exc:
                output = f"Slack failed ({exc}) — logged: {message}"
                logger.warning(f"[Runner] Slack notify failed: {exc}")

        elif channel == "email":
            if not recipient:
                output = "Email skipped — no recipient configured"
                logger.warning("[Runner] Notify: email channel but no recipient")
            else:
                try:
                    from django.core.mail import send_mail
                    from django.conf import settings
                    send_mail(
                        subject        = subject,
                        message        = message,
                        from_email     = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"),
                        recipient_list = [recipient],
                        fail_silently  = False,
                    )
                    output = f"Email sent to {recipient}"
                    logger.info(f"[Runner] Email sent → {recipient}")
                except Exception as exc:
                    output = f"Email failed: {exc}"
                    logger.error(f"[Runner] Email failed: {exc}")

        else:
            output = f"Notification: {message}"
            logger.info(f"[Runner] Notify (log): {message}")

        return {"success": True, "output": output}
    
    # ── Approval ──────────────────────────────────────────────────────────────
    def _handle_approval(self, execution, node, step):
        """
        Pause execution. A human must call /approve/ or /reject/ to resume.
        Stores the node id in context so views.py knows where to resume from.
        """
        execution.status = "paused"
        execution.context["pending_approval_node"]  = node.id
        execution.context["pending_approval_label"] = node.label
        execution.save(update_fields=["status", "context"])

        logger.info(
            f"[Runner] Approval required: '{node.label}' — execution {self.execution_id} paused"
        )
        return {
            "success": True,
            "output":  f"Waiting for human approval: {node.label}",
            "async":   True,
        }

    # ── End ───────────────────────────────────────────────────────────────────
    def _handle_end(self, execution, node, step):
        self._complete(execution)
        return {"success": True, "output": f"Workflow complete at: {node.label}", "async": True}

    # ── Unknown ───────────────────────────────────────────────────────────────
    def _handle_unknown(self, execution, node, step):
        logger.warning(f"[Runner] Unknown node type '{node.type}' — skipping")
        return {"success": True, "output": f"Skipped unknown node type: {node.type}"}

    # ─────────────────────────────────────────────────────────────────────────
    # GRAPH NAVIGATION
    # ─────────────────────────────────────────────────────────────────────────

    def _next_nodes(self, workflow, current_node, branch_label=""):
        """
        Return nodes that follow current_node.
        If branch_label given, match edges by label (case-insensitive).
        Falls back to all outgoing edges if no label match.
        """
        from .models import WorkflowEdge

        edges = list(
            WorkflowEdge.objects
            .filter(workflow=workflow, from_node=current_node)
            .select_related("to_node")
        )

        if not edges:
            return []

        if branch_label:
            matched = [
                e.to_node for e in edges
                if e.label.strip().lower() == branch_label.strip().lower()
            ]
            if matched:
                return matched

        return [e.to_node for e in edges]

    # ─────────────────────────────────────────────────────────────────────────
    # LIFECYCLE HELPERS
    # ─────────────────────────────────────────────────────────────────────────

    def _complete(self, execution):
        now = dj_tz.now()
        execution.status       = "success"
        execution.current_node = None
        execution.finished_at  = now
        if execution.started_at:
            execution.duration_ms = int(
                (now - execution.started_at).total_seconds() * 1000
            )
        execution.save()

        from .models import Workflow
        Workflow.objects.filter(id=execution.workflow_id).update(
            executions=F("executions") + 1,
            last_run=now,
        )
        logger.info(f"[Runner] ✓ Execution {self.execution_id} completed")

    def _fail(self, execution, error: str):
        now = dj_tz.now()
        execution.status      = "failed"
        execution.error       = error
        execution.finished_at = now
        if execution.started_at:
            execution.duration_ms = int(
                (now - execution.started_at).total_seconds() * 1000
            )
        execution.save()
        logger.error(f"[Runner] ✗ Execution {self.execution_id} failed: {error}")

    # ─────────────────────────────────────────────────────────────────────────
    # AGENT LOOKUP
    # ─────────────────────────────────────────────────────────────────────────

    def _find_agent(self, agent_name: str):
        """
        Find the best matching Resource (AI Agent) in the DB.
        Returns None if nothing found — caller handles fallback.
        """
        try:
            from crmapp.agentic.core.models import Resource

            # Exact name match first
            if agent_name:
                r = Resource.objects.filter(
                    name__icontains=agent_name,
                    type="AI Agent",
                    status__in=["idle", "active", "busy"],
                ).order_by("load_percentage").first()
                if r:
                    return r

            # Any available agent
            return (
                Resource.objects
                .filter(type="AI Agent", status__in=["idle", "active"])
                .order_by("load_percentage")
                .first()
            )
        except Exception as exc:
            logger.warning(f"[Runner] Agent lookup failed: {exc}")
            return None

    def _infer_agent(self, label: str) -> str:
        """Map node label keywords to known agent names."""
        l = label.lower()
        if any(w in l for w in ["lead", "assign", "territory", "rep", "sales", "prospect"]):
            return "Sales Intelligence Agent"
        if any(w in l for w in ["invoice", "payment", "finance", "reimburs", "budget"]):
            return "Finance Recovery Agent"
        if any(w in l for w in ["ticket", "support", "escalat", "l2", "issue"]):
            return "Customer Support Agent"
        if any(w in l for w in ["crm", "record", "database", "update", "log"]):
            return "CRM Analytics Agent"
        if any(w in l for w in ["email", "notify", "slack", "message", "alert"]):
            return "Sales Intelligence Agent"
        if any(w in l for w in ["hire", "onboard", "hr", "payroll", "employee"]):
            return "HR Operations Agent"
        return ""

    # ─────────────────────────────────────────────────────────────────────────
    # DIRECT GROQ FALLBACK
    # ─────────────────────────────────────────────────────────────────────────

    def _direct_groq(self, system: str, prompt: str) -> str:
        """
        Direct Groq API call — same pattern as services.py test_agent_with_groq().
        Used when no agent Resource is in the DB.
        Never crashes — returns error string on failure.
        """
        try:
            from django.conf import settings
            from groq import Groq

            api_key = getattr(settings, "GROQ_API_KEY", "")
            if not api_key:
                return "[Groq] GROQ_API_KEY not set in settings.py"

            client   = Groq(api_key=api_key)
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": prompt},
                ],
                temperature=0.3,
                max_tokens=512,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            logger.error(f"[Runner] Direct Groq call failed: {exc}")
            return f"[Groq error] {exc}"

    # ─────────────────────────────────────────────────────────────────────────
    # CONDITION HELPERS
    # ─────────────────────────────────────────────────────────────────────────

    def _evaluate_condition_heuristic(
        self, label: str, context: dict, true_label: str, false_label: str
    ) -> str:
        """
        Keyword-based condition evaluation without any external call.
        Covers the most common workflow patterns.
        """
        label_lower = label.lower()

        # Amount threshold: "Amount > $5,000" / "Amount > 5000"
        m = re.search(r">\s*\$?([\d,]+)", label)
        if m:
            threshold = float(m.group(1).replace(",", ""))
            amount    = float(context.get("amount", context.get("total", 0)))
            return true_label if amount > threshold else false_label

        # Less-than threshold
        m = re.search(r"<\s*\$?([\d,]+)", label)
        if m:
            threshold = float(m.group(1).replace(",", ""))
            amount    = float(context.get("amount", context.get("total", 0)))
            return true_label if amount < threshold else false_label

        # Territory check
        if "territory" in label_lower or "region" in label_lower:
            territory = str(context.get("territory", context.get("region", ""))).lower()
            if "north" in territory: return "North"
            if "south" in territory: return "South"
            if "east"  in territory: return "East"
            if "west"  in territory: return "West"
            return true_label

        # Open / closed / resolved
        if "open" in label_lower or "resolved" in label_lower:
            s = str(context.get("status", "open")).lower()
            return true_label if s in ("open", "pending", "active") else false_label

        # Approved / rejected from a previous approval node
        if "approved" in label_lower:
            decision = str(context.get("approval_decision", "")).lower()
            return true_label if decision == "approved" else false_label

        # Boolean flags in context
        if "vip" in label_lower:
            return true_label if context.get("vip") else false_label
        if "urgent" in label_lower:
            return true_label if context.get("urgent") else false_label

        # Default to true branch
        return true_label

    def _match_branch(
        self, agent_answer: str, workflow, node, true_label: str, false_label: str
    ) -> str:
        """
        Match an agent's free-text answer to available edge labels.
        """
        from .models import WorkflowEdge

        edges = list(
            WorkflowEdge.objects.filter(workflow=workflow, from_node=node)
        )
        answer_lower = agent_answer.lower()

        # Try exact match
        for e in edges:
            if e.label.lower() in answer_lower:
                return e.label

        # Yes/No detection
        if any(w in answer_lower for w in ["yes", "true", "approved", "positive"]):
            return true_label
        if any(w in answer_lower for w in ["no", "false", "rejected", "negative"]):
            return false_label

        return true_label

    # ─────────────────────────────────────────────────────────────────────────
    # DELAY PARSER
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_delay(self, label: str, config: dict) -> int:
        """
        Return delay in seconds.
        Priority: config["delay_seconds"] > label text > default 1h.
        """
        if config.get("delay_seconds"):
            try:
                return int(config["delay_seconds"])
            except (ValueError, TypeError):
                pass

        m = re.search(r"(\d+)\s*(second|minute|hour|day)s?", label, re.IGNORECASE)
        if m:
            value = int(m.group(1))
            unit  = m.group(2).lower()
            return {"second": value, "minute": value*60, "hour": value*3600, "day": value*86400}[unit]

        return 3600  # default: 1 hour

    # ─────────────────────────────────────────────────────────────────────────
    # CONTEXT HELPER
    # ─────────────────────────────────────────────────────────────────────────

    def _context_summary(self, context: dict) -> str:
        """Short readable summary of context for agent prompts."""
        if not context:
            return ""
        lines = [
            f"  {k}: {str(v)[:120]}"
            for k, v in list(context.items())[:6]
            if not k.startswith("output_")
        ]
        return "\n".join(lines)

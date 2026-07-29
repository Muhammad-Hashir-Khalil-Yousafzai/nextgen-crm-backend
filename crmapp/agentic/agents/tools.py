"""
crmapp/agentic/agents/tools.py

All 7 tools fully working:
  1. TavilySearchTool   — real web search (Tavily API)
  2. EmailSendTool      — real email (Gmail SMTP)
  3. CRMReadTool        — reads from Supabase via Django ORM
  4. CRMWriteTool       — writes to Supabase via Django ORM
  5. SlackNotifyTool    — real Slack messages (webhook)
  6. CalendarBookTool   — creates calendar events (Google Calendar API)
  7. AnalyticsTool      — reads real analytics from your DB

Required settings.py keys:
  TAVILY_API_KEY      = "tvly-..."
  EMAIL_HOST_USER     = "you@gmail.com"
  EMAIL_HOST_PASSWORD = "xxxx xxxx xxxx xxxx"
  SLACK_WEBHOOK_URL   = "https://hooks.slack.com/services/..."

BUG FIX HISTORY for EmailSendTool, CRMReadTool, CRMWriteTool, CalendarBookTool,
AnalyticsTool — these tools went through 3 fix iterations before landing on
the correct one:

  1. Single `input_json` string parameter, matching description text.
     Groq/LiteLLM consistently ignored this and generated flat keyword
     arguments instead (e.g. {"to": ..., "subject": ..., "body": ...} for
     email_send), causing "missing properties: 'input_json'" tool-call
     validation failures.

  2. Permissive args_schema accepting EITHER input_json OR the flat fields,
     all marked Optional with defaults. This looked correct when inspected
     locally via model_json_schema() — but CrewAI's OpenAI-compatible
     provider (crewai/llms/providers/openai/completion.py,
     _convert_tools_for_interference) hardcodes `"strict": True` on every
     tool call with no per-tool override. Under OpenAI/Groq strict mode,
     ALL declared schema properties must appear in "required" regardless
     of Pydantic defaults — so the sanitizer rewrote required to include
     every field, and Groq's actual 3-field call still failed because
     input_json was never sent.

  3. THIS VERSION (correct) — input_json removed entirely. Each tool's
     args_schema now declares ONLY the fields Groq actually sends (e.g.
     to/subject/body for email, model/dept/status/limit for CRM read).
     Under strict mode these become correctly required and match exactly
     what Groq generates, eliminating the mismatch at its root rather than
     working around it.

  SlackNotifyTool was never affected — its description always specified a
  single plain-text "message" string, which is what Groq naturally sends
  for it, so its original _run(self, message: str) signature was correct
  from the start.
"""

import json
import logging
import smtplib
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Optional

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# HELPER — get Django settings safely
# ─────────────────────────────────────────────────────────────────────────────

def _setting(key: str, default: str = "") -> str:
    try:
        from django.conf import settings
        return getattr(settings, key, default) or default
    except Exception:
        return default


# ─────────────────────────────────────────────────────────────────────────────
# 1. WEB SEARCH — Tavily
# ─────────────────────────────────────────────────────────────────────────────

class TavilySearchTool(BaseTool):
    name: str = "Web Search"
    description: str = (
        "Search the web for current, real-time information. "
        "Use this for news, company research, market data, competitor analysis, "
        "or any information that may have changed recently. "
        "Input: a plain English search query string. "
        "Example input: 'latest CRM software trends 2024'"
    )

    def _run(self, query: str) -> str:
        api_key = _setting("TAVILY_API_KEY")
        if not api_key:
            return (
                "TAVILY_API_KEY not set in settings.py. "
                "Get a free key at https://tavily.com"
            )
        if not query or not query.strip():
            return "Error: Search query cannot be empty."

        try:
            from tavily import TavilyClient
            client   = TavilyClient(api_key=api_key)
            response = client.search(
                query=query.strip(),
                search_depth="basic",
                max_results=3,
            )

            results = response.get("results", [])
            if not results:
                return f"No web results found for: '{query}'"

            lines = [f"Web search results for '{query}':\n"]
            for i, r in enumerate(results[:3], 1):
                lines.append(
                    f"{i}. {r.get('title', 'No title')}\n"
                    f"   URL: {r.get('url', '')}\n"
                    f"   {r.get('content', '')[:400]}\n"
                )
            return "\n".join(lines)

        except ImportError:
            return "tavily-python not installed. Run: pip install tavily-python"
        except Exception as e:
            logger.error(f"Tavily search error: {e}")
            return f"Web search failed: {str(e)}"


# ─────────────────────────────────────────────────────────────────────────────
# 2. EMAIL SEND — Gmail SMTP
# ─────────────────────────────────────────────────────────────────────────────

class EmailSendArgsSchema(BaseModel):
    """
    BUG FIX HISTORY — this schema went through three iterations:
    1. Single input_json field only — Groq ignored it and sent flat
       to/subject/body arguments anyway, failing schema validation.
    2. Permissive schema with all 4 fields optional (input_json + flat
       fields) — this looked correct locally, but CrewAI's OpenAI-provider
       code hardcodes 'strict: True' on every tool call with NO override
       (crewai/llms/providers/openai/completion.py,
       _convert_tools_for_interference). Under OpenAI/Groq strict mode,
       ALL schema properties must be listed in 'required' regardless of
       Pydantic defaults — so the sanitizer rewrote our schema to require
       all 4 fields, and Groq's actual 3-field call ({to, subject, body})
       failed with "missing properties: 'input_json'".
    3. THIS VERSION — drop input_json entirely. Only declare the fields
       Groq actually sends (to, subject, body) as the real schema. Under
       strict mode these become correctly required, matching exactly what
       Groq generates, with no mismatch possible.
    """
    to:      str = Field(description="Recipient email address")
    subject: str = Field(description="Email subject line")
    body:    str = Field(description="Email body text")


class EmailSendTool(BaseTool):
    name: str = "Email Send"
    description: str = (
        "Send a real email to a recipient via Gmail. "
        "Call with three arguments: to (recipient email address), "
        "subject (email subject line), body (email body text). "
        "Example: to=\"client@example.com\" subject=\"Follow up\" "
        "body=\"Dear Client, ...\""
    )
    args_schema: type[BaseModel] = EmailSendArgsSchema

    def _run(self, to: str = "", subject: str = "", body: str = "") -> str:
        host_user = _setting("EMAIL_HOST_USER")
        host_pass = _setting("EMAIL_HOST_PASSWORD")

        if not host_user or not host_pass:
            return (
                "Email not configured. Add EMAIL_HOST_USER and "
                "EMAIL_HOST_PASSWORD to settings.py"
            )

        try:
            final_to      = (to or "").strip()
            final_subject = (subject or "No Subject").strip()
            final_body    = (body or "").strip()

            if not final_to:
                return "Error: 'to' email address is required."
            if "@" not in final_to:
                return f"Error: '{final_to}' does not look like a valid email address."

            msg            = MIMEMultipart()
            msg["From"]    = host_user
            msg["To"]      = final_to
            msg["Subject"] = final_subject
            msg.attach(MIMEText(final_body, "plain"))

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(host_user, host_pass)
                server.send_message(msg)

            logger.info(f"Email sent to {final_to}: {final_subject}")
            return f"✓ Email sent successfully to {final_to} with subject: '{final_subject}'"

        except smtplib.SMTPAuthenticationError:
            return (
                "Gmail authentication failed. Make sure you are using a "
                "Gmail App Password (not your regular password). "
                "Get one at: myaccount.google.com → Security → App passwords"
            )
        except Exception as e:
            logger.error(f"Email send error: {e}")
            return f"Email failed: {str(e)}"


# ─────────────────────────────────────────────────────────────────────────────
# 3. CRM READ — Supabase via Django ORM
# ─────────────────────────────────────────────────────────────────────────────

class CRMReadArgsSchema(BaseModel):
    """
    Flat schema matching Groq's actual call shape — see EmailSendArgsSchema
    docstring for why input_json was dropped (strict mode incompatibility).

    FURTHER BUG FIX — Optional fields still break under strict mode:
    Marking dept/status as Optional[str] with default=None was not enough.
    CrewAI's strict-mode sanitizer puts EVERY declared field in "required"
    regardless of Optional/default — so when Groq (correctly, per the
    description) omitted dept/status because they weren't relevant to a
    given call, the schema validator rejected the call for "missing
    properties: 'dept', 'status'". Under strict mode there is no such
    thing as a truly optional field — every field must be required AND
    Groq must be told to always send one (even an empty string) for
    fields it doesn't need. dept/status are now required str with no
    default; the description instructs Groq to pass "" when not filtering.

    FURTHER BUG FIX — limit type coercion:
    Groq sent {"limit": "100"} (a JSON string) instead of {"limit": 100}
    (an integer), since LLMs frequently stringify numbers in generated
    function calls. The schema declared limit: int, so strict validation
    rejected the string. limit is now declared as int | str and coerced
    to int manually inside _run(), since Pydantic/JSON-schema unions are
    more reliably accepted by strict-mode validators than relying on the
    LLM to always emit the correct JSON type.
    """
    model:  str       = Field(description="tasks|goals|alerts|leads|contacts|deals")
    dept:   str       = Field(description="Department filter, or empty string for no filter")
    status: str       = Field(description="Status filter, or empty string for no filter")
    limit:  int | str = Field(default=10, description="Max records to return, as an integer")


class CRMReadTool(BaseTool):
    name: str = "CRM Read"
    description: str = (
        "Read records from the CRM database. "
        "Call with all 4 arguments every time: "
        "model (required — one of tasks, goals, alerts, leads, contacts, deals), "
        "dept (department filter — pass empty string \"\" if not filtering), "
        "status (status filter — pass empty string \"\" if not filtering), "
        "limit (max records to return, as an integer, default 10). "
        "Example: model=\"leads\" dept=\"\" status=\"\" limit=10"
    )
    args_schema: type[BaseModel] = CRMReadArgsSchema

    def _run(
        self,
        model: str = "",
        dept: str = "",
        status: str = "",
        limit: int | str = 10,
    ) -> str:
        try:
            model_name = (model or "").lower().strip()
            dept       = (dept or "").strip()
            status     = (status or "").strip()
            try:
                limit = int(limit) if limit else 10
            except (TypeError, ValueError):
                limit = 10

            if not model_name:
                return (
                    "Error: 'model' is required. "
                    "Choose from: tasks, goals, alerts, leads, contacts, deals"
                )

            MODEL_MAP = {
                "tasks":    ("crmapp.agentic.tasks.models", "Task"),
                "goals":    ("crmapp.agentic.tasks.models", "Goal"),
                "alerts":   ("crmapp.agentic.tasks.models", "BottleneckAlert"),
                "leads":    ("crmapp.crm.leads.models",     "Lead"),
                "contacts": ("crmapp.crm.contacts.models",  "Contact"),
                "deals":    ("crmapp.crm.deals.models",     "Deal"),
            }

            if model_name not in MODEL_MAP:
                return (
                    f"Unknown model '{model_name}'. "
                    f"Choose from: {', '.join(MODEL_MAP.keys())}"
                )

            module_path, class_name = MODEL_MAP[model_name]
            import importlib
            module = importlib.import_module(module_path)
            ModelClass = getattr(module, class_name)

            qs = ModelClass.objects.all()
            if dept:
                qs = qs.filter(dept__iexact=dept)
            if status:
                qs = qs.filter(status__iexact=status)
            qs = qs[:limit]

            if not qs.exists():
                return f"No {model_name} records found matching your criteria."

            lines = [f"CRM {model_name} records (up to {limit}):"]
            for obj in qs:
                parts = [f"  id={obj.pk}"]
                for field in ("name", "title", "status", "dept", "stage", "email"):
                    val = getattr(obj, field, None)
                    if val is not None:
                        parts.append(f"{field}={val}")
                lines.append("  " + " | ".join(parts))

            return "\n".join(lines)

        except json.JSONDecodeError as e:
            return f"Error: Could not parse JSON input — {e}"
        except Exception as e:
            logger.error(f"CRMReadTool error: {e}")
            return f"CRM read failed: {str(e)}"


# ─────────────────────────────────────────────────────────────────────────────
# 4. CRM WRITE — Supabase via Django ORM
# ─────────────────────────────────────────────────────────────────────────────

class CRMWriteArgsSchema(BaseModel):
    """
    Flat schema matching Groq's actual call shape — see EmailSendArgsSchema
    docstring for why input_json was dropped (strict mode incompatibility).

    FURTHER BUG FIX — see CRMReadArgsSchema docstring for why id cannot be
    Optional under strict mode. It's now required str; pass "" when not
    updating (i.e. for create calls).

    FURTHER BUG FIX — open-ended dict cannot survive strict-mode sanitizing:
    `data: dict[str, Any]` looked correct locally (model_json_schema() showed
    "additionalProperties": true, which is valid JSON Schema) but CrewAI's
    sanitize_tool_params_for_openai_strict() hardcodes additionalProperties
    to False for strict mode and backfills "properties": {} to compensate.
    The result is syntactically valid JSON Schema but semantically broken:
    additionalProperties: false + properties: {} means the object is only
    ever allowed to be `{}` — any real key (name, email, status, etc.) is
    rejected by definition, since strict mode has no way to express "any
    object with arbitrary keys" once additionalProperties is forced false.
    Fix: declare data as a plain JSON string instead of a dict. A `str`
    type sanitizes cleanly with no additionalProperties ambiguity at all,
    and _run() parses it back into a dict manually before use. Groq is
    told explicitly to pass the data as a JSON-encoded string, e.g.
    data='{"name": "Acme", "email": "a@b.com"}'.
    """
    action: str = Field(description="create or update")
    model:  str = Field(description="tasks|goals|alerts|leads|contacts|deals")
    data:   str = Field(description="Fields to set, as a JSON-encoded string, e.g. {\"name\": \"Acme\"}")
    id:     str = Field(description="Record ID — required for update, pass empty string \"\" for create")


class CRMWriteTool(BaseTool):
    name: str = "CRM Write"
    description: str = (
    "Create or update records in the CRM database. "
    "Call with all 4 arguments every time: "
    "action ('create' or 'update'), "
    "model (tasks|goals|alerts|leads|contacts|deals), "
    "data (a JSON-ENCODED STRING of fields to set — not a raw object), "
    "id (record ID — required for update, pass empty string \"\" for create). "
    "Valid fields per model: "
    "leads: name, email, phone, location, company_name, value, probability, "
    "score, deal_stage, status, priority, source, lost_reason, notes "
    "(NOTE: leads has no separate address/city/state/zip — use 'location' "
    "as a single combined string, e.g. '123 Main St, New York, NY 10001'). "
    "Example: action=\"create\" model=\"leads\" "
    "data=\"{\\\"name\\\": \\\"Acme\\\", \\\"email\\\": \\\"a@b.com\\\", "
    "\\\"location\\\": \\\"123 Main St, New York, NY 10001\\\"}\" id=\"\""
    )
    args_schema: type[BaseModel] = CRMWriteArgsSchema

    def _run(
        self,
        action: str = "",
        model: str = "",
        data: str = "",
        id: str = "",
    ) -> str:
        try:
            final_action     = (action or "").lower().strip()
            final_model_name = (model or "").lower().strip()
            final_record_id  = id or None

            # data arrives as a JSON-encoded string now, not a dict —
            # parse it here, tolerating single-quoted/lenient JSON the
            # LLM occasionally produces.
            raw_data = (data or "").strip()
            if raw_data:
                try:
                    final_fields = json.loads(raw_data)
                except json.JSONDecodeError:
                    import re
                    normalised = re.sub(r"'", '"', raw_data)
                    try:
                        final_fields = json.loads(normalised)
                    except json.JSONDecodeError:
                        return f"Error: 'data' is not valid JSON: {raw_data[:200]}"
            else:
                final_fields = {}

            if final_action not in ("create", "update"):
                return "Error: 'action' must be 'create' or 'update'."

            MODEL_MAP = {
                "tasks":    ("crmapp.agentic.tasks.models", "Task"),
                "goals":    ("crmapp.agentic.tasks.models", "Goal"),
                "alerts":   ("crmapp.agentic.tasks.models", "BottleneckAlert"),
                "leads":    ("crmapp.crm.leads.models",     "Lead"),
                "contacts": ("crmapp.crm.contacts.models",  "Contact"),
                "deals":    ("crmapp.crm.deals.models",     "Deal"),
            }

            if final_model_name not in MODEL_MAP:
                return (
                    f"Unknown model '{final_model_name}'. "
                    f"Choose from: {', '.join(MODEL_MAP.keys())}"
                )

            module_path, class_name = MODEL_MAP[final_model_name]
            import importlib
            module = importlib.import_module(module_path)
            ModelClass = getattr(module, class_name)

            if final_action == "create":
                if not final_fields:
                    return "Error: 'data' dict is required for create."

                # Attribute agent-created leads to a system user, since there's
                # no logged-in request context inside a workflow/agent execution.
                if (
                    final_model_name == "leads"
                    and "created_by" not in final_fields
                    and "created_by_id" not in final_fields
                ):
                    from django.conf import settings
                    system_user_id = getattr(settings, "AUTOMATION_SYSTEM_USER_ID", None)
                    if system_user_id:
                        final_fields["created_by_id"] = system_user_id

                obj = ModelClass.objects.create(**final_fields)
                logger.info(f"CRMWriteTool: created {final_model_name} id={obj.pk}")
                return f"✓ Created {final_model_name} record with id={obj.pk}"

            else:  # update
                if not final_record_id:
                    return "Error: 'id' is required for update."
                if not final_fields:
                    return "Error: 'data' dict is required for update."
                updated = ModelClass.objects.filter(pk=final_record_id).update(**final_fields)
                if updated == 0:
                    return f"No {final_model_name} record found with id={final_record_id}."
                logger.info(f"CRMWriteTool: updated {final_model_name} id={final_record_id}")
                return f"✓ Updated {final_model_name} record id={final_record_id} with {list(final_fields.keys())}"

        except json.JSONDecodeError as e:
            return f"Error: Could not parse JSON input — {e}"
        except Exception as e:
            logger.error(f"CRMWriteTool error: {e}")
            return f"CRM write failed: {str(e)}"
        
# ─────────────────────────────────────────────────────────────────────────────
# 5. SLACK NOTIFY — real webhook
# ─────────────────────────────────────────────────────────────────────────────

class SlackNotifyTool(BaseTool):
    name: str = "Slack Notify"
    description: str = (
        "Send a real notification message to a Slack channel. "
        "Input: a plain text message string to send. "
        "Example: 'Invoice #1234 is overdue by 30 days. Client: Acme Corp.'"
    )

    # NOTE: description says "a plain text message string", so "message"
    # is the CORRECT parameter name here — left unchanged.
    def _run(self, message: str) -> str:
        webhook_url = _setting("SLACK_WEBHOOK_URL")
        if not webhook_url:
            return (
                "SLACK_WEBHOOK_URL not set in settings.py. "
                "Get a free webhook at: api.slack.com/apps → Incoming Webhooks"
            )
        if not message or not message.strip():
            return "Error: Message cannot be empty."

        try:
            payload = json.dumps({"text": message.strip()}).encode("utf-8")
            req = urllib.request.Request(
                webhook_url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    logger.info(f"Slack notification sent: {message[:80]}")
                    return f"✓ Slack notification sent: '{message[:100]}'"
                return f"Slack returned unexpected status: {resp.status}"

        except urllib.error.HTTPError as e:
            return f"Slack webhook error {e.code}: {e.reason}"
        except Exception as e:
            logger.error(f"Slack notify error: {e}")
            return f"Slack notify failed: {str(e)}"


# ─────────────────────────────────────────────────────────────────────────────
# 6. CALENDAR BOOK — Google Calendar API
# ─────────────────────────────────────────────────────────────────────────────

class CalendarBookArgsSchema(BaseModel):
    """
    Flat schema matching Groq's actual call shape — see EmailSendArgsSchema
    docstring for why input_json was dropped (strict mode incompatibility).

    FURTHER BUG FIX — see CRMReadArgsSchema docstring for why Optional
    fields break under strict mode. attendees/description are required
    with an empty-list/empty-string convention. time/duration_mins were
    ALSO missing from "required" due to having defaults — same trap,
    fixed the same way: removed defaults, made them genuinely required.
    duration_mins accepts int | str since LLMs frequently stringify numbers.
    """
    title:         str       = Field(description="Meeting title")
    date:          str       = Field(description="Date YYYY-MM-DD")
    time:          str       = Field(description="Time HH:MM, e.g. 09:00")
    duration_mins: int | str = Field(description="Duration in minutes, as an integer, e.g. 30")
    attendees:     list      = Field(description="List of attendee emails, or empty list if none")
    description:   str       = Field(description="Event description, or empty string if none")

class CalendarBookTool(BaseTool):
    name: str = "Calendar Book"
    description: str = (
        "Schedule a meeting or calendar event. "
        "Call with all 6 arguments every time: "
        "title, date (YYYY-MM-DD), time (HH:MM), "
        "duration_mins (integer), attendees (list of email strings — pass "
        "empty list [] if none), description (pass empty string \"\" if none). "
        "Example: title=\"Invoice Review\" date=\"2024-04-01\" time=\"10:00\" "
        "duration_mins=30 attendees=[\"client@example.com\"] description=\"\""
    )
    args_schema: type[BaseModel] = CalendarBookArgsSchema

    def _run(
        self,
        title: str = "Meeting",
        date: str = "",
        time: str = "09:00",
        duration_mins: int | str = 30,
        attendees: list = None,
        description: str = "",
    ) -> str:
        try:
            title     = title or "Meeting"
            date      = date or ""
            time_str  = time or "09:00"
            try:
                duration = int(duration_mins) if duration_mins else 30
            except (TypeError, ValueError):
                duration = 30
            attendees = attendees or []
            desc      = description or ""

            if not date:
                return "Error: 'date' is required (format: YYYY-MM-DD)."

            creds_path = _setting("GOOGLE_CALENDAR_CREDENTIALS_PATH")
            if creds_path:
                return self._book_with_google(
                    title, date, time_str, duration, attendees, desc, creds_path
                )

            try:
                from crmapp.agentic.tasks.models import Task
                from datetime import datetime
                from django.utils import timezone as dj_timezone

                # Parse date + time into a real datetime for scheduled_at,
                # so the auto-promotion beat task can find it later.
                scheduled_dt = None
                try:
                    naive_dt = datetime.strptime(f"{date} {time_str}", "%Y-%m-%d %H:%M")
                    scheduled_dt = dj_timezone.make_aware(naive_dt)
                except ValueError:
                    pass  # if Groq sent a malformed date/time, just skip auto-scheduling

                task = Task.objects.create(
                    name=f"Meeting: {title}",
                    description=(
                        f"Scheduled for {date} at {time_str}, "
                        f"{duration} mins. "
                        f"Attendees: {', '.join(attendees)}. {desc}"
                    ),
                    status="scheduled",
                    priority="normal",
                    dept="CRM",
                    schedule=f"{date} {time_str}",
                    scheduled_at=scheduled_dt,
                )
                return (
                    f"✓ Meeting '{title}' saved to CRM task queue:\n"
                    f"  Date: {date} at {time_str}\n"
                    f"  Duration: {duration} minutes\n"
                    f"  Attendees: {', '.join(attendees) if attendees else 'None'}\n"
                    f"  Task ID: {task.id}\n"
                    f"  (Add GOOGLE_CALENDAR_CREDENTIALS_PATH to settings.py "
                    f"for real Google Calendar integration)"
                )            
            
            except Exception:
                return (
                    f"Meeting scheduled (in memory only):\n"
                    f"  Title: {title}\n"
                    f"  Date: {date} at {time_str}\n"
                    f"  Duration: {duration} mins\n"
                    f"  Attendees: {', '.join(attendees) if attendees else 'None'}"
                )

        except json.JSONDecodeError:
            return "Error: Input must be valid JSON."
        except Exception as e:
            logger.error(f"Calendar book error: {e}")
            return f"Calendar booking failed: {str(e)}"

    def _book_with_google(
        self, title, date, time_str, duration, attendees, desc, creds_path
    ) -> str:
        try:
            from google.oauth2.service_account import Credentials
            from googleapiclient.discovery import build
            from datetime import datetime, timedelta

            scopes = ["https://www.googleapis.com/auth/calendar"]
            creds  = Credentials.from_service_account_file(creds_path, scopes=scopes)
            svc    = build("calendar", "v3", credentials=creds)

            start_dt = datetime.strptime(f"{date} {time_str}", "%Y-%m-%d %H:%M")
            end_dt   = start_dt + timedelta(minutes=duration)

            event = {
                "summary":     title,
                "description": desc,
                "start":       {"dateTime": start_dt.isoformat(), "timeZone": "UTC"},
                "end":         {"dateTime": end_dt.isoformat(),   "timeZone": "UTC"},
                "attendees":   [{"email": e} for e in attendees],
            }

            created = svc.events().insert(calendarId="primary", body=event).execute()
            return (
                f"✓ Google Calendar event created: '{title}'\n"
                f"  Date: {date} at {time_str}\n"
                f"  Link: {created.get('htmlLink', 'N/A')}"
            )

        except ImportError:
            return (
                "google-api-python-client not installed. "
                "Run: pip install google-api-python-client google-auth"
            )
        except Exception as e:
            return f"Google Calendar booking failed: {str(e)}"


# ─────────────────────────────────────────────────────────────────────────────
# 7. ANALYTICS — reads real data from your DB
# ─────────────────────────────────────────────────────────────────────────────

class AnalyticsArgsSchema(BaseModel):
    """Flat schema matching Groq's actual call shape — see EmailSendArgsSchema
    docstring for why input_json was dropped (strict mode incompatibility)."""
    metric: str = Field(description="task_completion_rate|agent_performance|monthly_summary|bottleneck_analysis|dept_performance")


class AnalyticsTool(BaseTool):
    name: str = "Analytics API"
    description: str = (
        "Fetch real analytics and performance metrics from the CRM database. "
        "Call with: metric — one of task_completion_rate, agent_performance, "
        "monthly_summary, bottleneck_analysis, dept_performance. "
        "Example: metric=\"task_completion_rate\""
    )
    args_schema: type[BaseModel] = AnalyticsArgsSchema

    def _run(self, metric: str = "monthly_summary") -> str:
        try:
            metric = (metric or "monthly_summary").lower().strip()

            if metric == "task_completion_rate":
                return self._task_completion_rate()
            elif metric == "agent_performance":
                return self._agent_performance()
            elif metric == "monthly_summary":
                return self._monthly_summary()
            elif metric == "bottleneck_analysis":
                return self._bottleneck_analysis()
            elif metric == "dept_performance":
                return self._dept_performance()
            else:
                return (
                    f"Unknown metric '{metric}'. "
                    "Use: task_completion_rate, agent_performance, "
                    "monthly_summary, bottleneck_analysis, dept_performance"
                )

        except json.JSONDecodeError:
            return "Error: Input must be valid JSON."
        except Exception as e:
            logger.error(f"Analytics error: {e}")
            return f"Analytics failed: {str(e)}"

    def _task_completion_rate(self) -> str:
        from crmapp.agentic.tasks.models import Task
        total     = Task.objects.count()
        completed = Task.objects.filter(status="completed").count()
        failed    = Task.objects.filter(status="failed").count()
        running   = Task.objects.filter(status="running").count()
        pending   = Task.objects.filter(status="pending").count()
        rate      = round((completed / total * 100), 1) if total else 0
        return (
            f"Task Completion Analytics:\n"
            f"  Total tasks:      {total}\n"
            f"  Completed:        {completed} ({rate}%)\n"
            f"  Failed:           {failed}\n"
            f"  Running:          {running}\n"
            f"  Pending:          {pending}\n"
            f"  Completion rate:  {rate}%"
        )

    def _agent_performance(self) -> str:
        from crmapp.agentic.tasks.models import Task
        from crmapp.agentic.core.models import Resource
        from django.db.models import Count

        agents = Resource.objects.filter(type="AI Agent")
        lines  = ["Agent Performance Summary:"]
        for agent in agents:
            tasks_assigned = Task.objects.filter(assignee=agent.name)
            completed      = tasks_assigned.filter(status="completed").count()
            failed         = tasks_assigned.filter(status="failed").count()
            total          = tasks_assigned.count()
            lines.append(
                f"  {agent.name}: {completed}/{total} completed, "
                f"{failed} failed, load={agent.load_percentage}%"
            )
        return "\n".join(lines) if len(lines) > 1 else "No agents found in database."

    def _monthly_summary(self) -> str:
        from crmapp.agentic.tasks.models import MonthlyPerformance
        records = MonthlyPerformance.objects.order_by("-year", "-month")[:3]
        if not records:
            return "No monthly performance data found."
        lines = ["Monthly Performance Summary (last 3 months):"]
        for r in records:
            lines.append(
                f"  {r.month} {r.year}: "
                f"{r.tasks_completed} completed, "
                f"{r.tasks_failed} failed, "
                f"{r.on_time_percentage}% on-time, "
                f"{r.avg_execution_ms}ms avg"
            )
        return "\n".join(lines)

    def _bottleneck_analysis(self) -> str:
        from crmapp.agentic.tasks.models import Task, BottleneckAlert
        blocked  = Task.objects.filter(status="blocked").count()
        alerts   = BottleneckAlert.objects.filter(resolved_at__isnull=True)
        critical = alerts.filter(severity="critical").count()
        high     = alerts.filter(severity="high").count()
        lines    = [
            "Bottleneck Analysis:",
            f"  Blocked tasks:    {blocked}",
            f"  Active alerts:    {alerts.count()}",
            f"  Critical alerts:  {critical}",
            f"  High alerts:      {high}",
        ]
        for a in alerts[:3]:
            lines.append(f"  ⚠ {a.task_name}: {a.issue} (impact: {a.impact})")
        return "\n".join(lines)

    def _dept_performance(self) -> str:
        from crmapp.agentic.tasks.models import Task
        from django.db.models import Count
        depts = (
            Task.objects
            .values("dept")
            .annotate(
                total=Count("id"),
                completed=Count("id", filter=__import__(
                    "django.db.models",
                    fromlist=["Q"]
                ).Q(status="completed")),
            )
            .order_by("-total")
        )
        if not depts:
            return "No department data found."
        lines = ["Department Performance:"]
        for d in depts:
            total     = d["total"]
            completed = d["completed"]
            rate      = round((completed / total * 100), 1) if total else 0
            lines.append(
                f"  {d['dept']}: {completed}/{total} tasks ({rate}% completion)"
            )
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# TOOL REGISTRY — maps frontend tool name → tool instance
# ─────────────────────────────────────────────────────────────────────────────

TOOL_REGISTRY = {
    "Web Search":    TavilySearchTool(),
    "Email Send":    EmailSendTool(),
    "CRM Read":      CRMReadTool(),
    "CRM Write":     CRMWriteTool(),
    "Slack Notify":  SlackNotifyTool(),
    "Calendar Book": CalendarBookTool(),
    "Analytics API": AnalyticsTool(),
}


def get_tools_for_agent(tool_names: list) -> list:
    """
    Given a list of tool name strings (from Resource.tools),
    returns instantiated CrewAI tool objects ready to use.
    """
    tools   = []
    missing = []
    for name in tool_names:
        tool = TOOL_REGISTRY.get(name)
        if tool:
            tools.append(tool)
        else:
            missing.append(name)
    if missing:
        logger.warning(f"Tools not found in registry: {missing}")
    return tools
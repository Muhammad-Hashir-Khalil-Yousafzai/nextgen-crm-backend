"""
crmapp/agentic/agents/management/commands/seed_agents.py

Seeds the database with:
  - 5 default AI agent Resources
  - Their AgentConfig rows
  - All 7 AgentTool rows

Run with:
  python manage.py seed_agents
"""

from django.core.management.base import BaseCommand
from django.utils import timezone


DEFAULT_AGENTS = [
    {
        "name":      "Sales Intelligence Agent",
        "role":      "Sales Analyst — researches leads and qualifies prospects",
        "goal":      "Identify and qualify high-value sales leads to increase pipeline by 30%",
        "backstory": "Expert sales intelligence specialist with deep knowledge of B2B lead generation and CRM systems.",
        "tools":     ["Web Search", "CRM Read", "CRM Write", "Email Send"],
        "color":     "#3a9aab",
        "dept":      "Sales",
        "skills":    ["Lead Scoring", "CRM Write", "Email Send", "Web Search"],
        "llm":       "groq/llama-3.3-70b-versatile",
        "priority":  "high",
    },
    {
        "name":      "Customer Support Agent",
        "role":      "Support Specialist — resolves tickets and routes escalations",
        "goal":      "Resolve 95% of support tickets within SLA and reduce escalations by 40%",
        "backstory": "Experienced support specialist trained on CRM data and escalation procedures.",
        "tools":     ["CRM Read", "CRM Write", "Email Send", "Slack Notify"],
        "color":     "#4ade80",
        "dept":      "Support",
        "skills":    ["Ticket Route", "SLA Monitor", "Email Send", "Escalation"],
        "llm":       "groq/llama-3.3-70b-versatile",
        "priority":  "critical",
    },
    {
        "name":      "Finance Recovery Agent",
        "role":      "Finance Specialist — recovers overdue invoices and tracks payments",
        "goal":      "Recover 80% of overdue invoices and reduce outstanding AR by 60%",
        "backstory": "Expert in B2B collections and financial recovery with 10 years of experience.",
        "tools":     ["Email Send", "CRM Read", "CRM Write", "Slack Notify"],
        "color":     "#f97316",
        "dept":      "Finance",
        "skills":    ["Invoice Monitor", "Email Sequence", "ERP Sync", "CRM Alert"],
        "llm":       "groq/llama-3.3-70b-versatile",
        "priority":  "high",
    },
    {
        "name":      "Marketing Automation Agent",
        "role":      "Marketing Specialist — runs campaigns and analyses performance",
        "goal":      "Increase campaign ROI by 25% through automated A/B testing and segment targeting",
        "backstory": "Data-driven marketing specialist with expertise in campaign automation and analytics.",
        "tools":     ["Web Search", "Analytics API", "Email Send", "CRM Read"],
        "color":     "#a78bfa",
        "dept":      "Marketing",
        "skills":    ["Campaign Trigger", "A/B Test", "Segment Query", "Budget Optimize"],
        "llm":       "groq/llama-3.3-70b-versatile",
        "priority":  "normal",
    },
    {
        "name":      "CRM Analytics Agent",
        "role":      "Data Analyst — generates reports and monitors churn signals",
        "goal":      "Reduce churn by 20% through early detection and proactive outreach",
        "backstory": "Analytics specialist trained on CRM data patterns and predictive modelling.",
        "tools":     ["CRM Read", "Analytics API", "Slack Notify"],
        "color":     "#38bdf8",
        "dept":      "Analytics",
        "skills":    ["Churn Score Monitor", "Data Analysis", "Report Generation", "CRM Alert"],
        "llm":       "groq/mixtral-8x7b-32768",
        "priority":  "normal",
    },
]


DEFAULT_TOOLS = [
    {
        "tool_id":      "web_search",
        "name":         "Web Search",
        "icon":         "🔍",
        "category":     "Research",
        "description":  "Search the web via Tavily API — free, built for AI agents",
        "requires_key": "TAVILY_API_KEY",
    },
    {
        "tool_id":      "email",
        "name":         "Email Send",
        "icon":         "📧",
        "category":     "Communication",
        "description":  "Send emails via Gmail SMTP",
        "requires_key": "EMAIL_HOST_PASSWORD",
    },
    {
        "tool_id":      "crm_read",
        "name":         "CRM Read",
        "icon":         "📖",
        "category":     "CRM",
        "description":  "Read CRM database records via Django ORM",
        "requires_key": "",
    },
    {
        "tool_id":      "crm_write",
        "name":         "CRM Write",
        "icon":         "✏️",
        "category":     "CRM",
        "description":  "Write to CRM database via Django ORM",
        "requires_key": "",
    },
    {
        "tool_id":      "slack",
        "name":         "Slack Notify",
        "icon":         "💬",
        "category":     "Communication",
        "description":  "Send Slack notifications via webhook",
        "requires_key": "SLACK_WEBHOOK_URL",
    },
    {
        "tool_id":      "calendar",
        "name":         "Calendar Book",
        "icon":         "📅",
        "category":     "Productivity",
        "description":  "Schedule meetings (extend with Google Calendar API)",
        "requires_key": "",
    },
    {
        "tool_id":      "analytics",
        "name":         "Analytics API",
        "icon":         "📈",
        "category":     "Data",
        "description":  "Fetch analytics data (extend with your analytics provider)",
        "requires_key": "",
    },
]


class Command(BaseCommand):
    help = "Seeds default agents and tools into the database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all existing agents before seeding",
        )

    def handle(self, *args, **options):
        from crmapp.agentic.core.models import Resource
        from crmapp.agentic.agents.models import AgentConfig, AgentTool

        if options["clear"]:
            Resource.objects.filter(metadata__is_custom=False).delete()
            AgentTool.objects.all().delete()
            self.stdout.write(self.style.WARNING("Cleared existing default agents and tools."))

        # ── Seed Tools ────────────────────────────────────────────────────────
        self.stdout.write("Seeding agent tools...")
        for tool_data in DEFAULT_TOOLS:
            obj, created = AgentTool.objects.update_or_create(
                tool_id=tool_data["tool_id"],
                defaults=tool_data,
            )
            status_str = "Created" if created else "Updated"
            self.stdout.write(f"  {status_str}: {obj.name}")

        # ── Seed Agents ───────────────────────────────────────────────────────
        self.stdout.write("\nSeeding default agents...")
        for agent_data in DEFAULT_AGENTS:
            extra = {
                "is_custom":   False,
                "dept":        agent_data["dept"],
                "role":        agent_data["role"],
                "goal":        agent_data["goal"],
                "backstory":   agent_data["backstory"],
                "skills":      agent_data["skills"],
                "tools":       agent_data["tools"],
                "llm":         agent_data["llm"],
                "temperature": 0.3,
                "max_tokens":  1024,
                "priority":    agent_data["priority"],
                "color":       agent_data["color"],
            }

            resource, created = Resource.objects.update_or_create(
                name=agent_data["name"],
                defaults={
                    "type":      "ai_agent",
                    "status":    "idle",
                    "role":      agent_data["role"],
                    "goal":      agent_data["goal"],
                    "backstory": agent_data["backstory"],
                    "tools":     agent_data["tools"],
                    "color":     agent_data["color"],
                    "metadata":  extra,
                },
            )

            AgentConfig.objects.update_or_create(
                resource=resource,
                defaults={
                    "llm":         agent_data["llm"],
                    "temperature": 0.3,
                    "max_tokens":  1024,
                    "skills":      agent_data["skills"],
                    "dept":        agent_data["dept"],
                    "priority":    agent_data["priority"],
                },
            )

            status_str = "Created" if created else "Updated"
            self.stdout.write(f"  {status_str}: {resource.name} [{agent_data['dept']}]")

        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Done! {len(DEFAULT_TOOLS)} tools, {len(DEFAULT_AGENTS)} agents seeded.\n"
            f"   Test at: http://localhost:8000/api/agentic/agents/resources/"
        ))
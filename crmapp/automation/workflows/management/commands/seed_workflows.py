"""
python manage.py seed_workflows

Seeds the database with:
  - 4 ready-to-run workflows (Lead Assignment, Invoice Approval,
    Ticket Escalation, Employee Onboarding)
  - AI Agent Resources so the executor always finds an agent

Run once after first migration.
"""

from django.core.management.base import BaseCommand


AGENTS = [
    {
        "name":      "Sales Intelligence Agent",
        "role":      "Sales Automation Expert",
        "goal":      "Assign leads, qualify prospects, and update CRM records accurately.",
        "backstory": "Expert in CRM data, lead scoring, and territory management.",
        "tools":     ["crm_read", "crm_write", "slack_notify"],
        "dept":      "CRM",
    },
    {
        "name":      "Finance Recovery Agent",
        "role":      "Finance Operations Specialist",
        "goal":      "Process invoices, validate amounts, and route approvals correctly.",
        "backstory": "Expert in financial workflows, approval hierarchies, and payment processing.",
        "tools":     ["crm_read", "crm_write", "email_send"],
        "dept":      "Finance",
    },
    {
        "name":      "Customer Support Agent",
        "role":      "Support Escalation Specialist",
        "goal":      "Resolve and escalate support tickets based on SLA and priority.",
        "backstory": "Expert in ticket triage, escalation paths, and customer communication.",
        "tools":     ["crm_read", "crm_write", "slack_notify", "email_send"],
        "dept":      "Support",
    },
    {
        "name":      "CRM Analytics Agent",
        "role":      "CRM Data Analyst",
        "goal":      "Read, update, and analyse CRM records to keep data accurate.",
        "backstory": "Expert in CRM data pipelines, deduplication, and reporting.",
        "tools":     ["crm_read", "crm_write", "analytics"],
        "dept":      "CRM",
    },
    {
        "name":      "HR Operations Agent",
        "role":      "HR Process Coordinator",
        "goal":      "Manage onboarding, offboarding, and HR workflow automation.",
        "backstory": "Expert in HR processes, employee lifecycle, and compliance.",
        "tools":     ["crm_write", "email_send", "slack_notify"],
        "dept":      "HR",
    },
]

WORKFLOWS = [
    {
        "name": "Lead Auto-Assignment", "category": "CRM", "status": "active",
        "description": "Auto-assign new leads based on territory",
        "nodes": [
            {"type": "trigger",   "label": "New Lead Created",     "x": 80,   "y": 110},
            {"type": "condition", "label": "Check Territory",       "x": 300,  "y": 110,
             "config": {"true_branch": "North", "false_branch": "South"}},
            {"type": "action",    "label": "Assign North Rep",      "x": 520,  "y": 45,
             "config": {"agent_name": "Sales Intelligence Agent",
                        "task_description": "Assign this lead to the North territory representative and update CRM."}},
            {"type": "action",    "label": "Assign South Rep",      "x": 520,  "y": 175,
             "config": {"agent_name": "Sales Intelligence Agent",
                        "task_description": "Assign this lead to the South territory representative and update CRM."}},
            {"type": "notify",    "label": "Notify Rep via Email",  "x": 740,  "y": 110,
             "config": {"channel": "slack",
                        "message": "New lead assigned. Check your CRM for details."}},
            {"type": "end",       "label": "Done",                  "x": 960,  "y": 110},
        ],
        "edges": [
            {"from": 0, "to": 1, "label": ""},
            {"from": 1, "to": 2, "label": "North"},
            {"from": 1, "to": 3, "label": "South"},
            {"from": 2, "to": 4, "label": ""},
            {"from": 3, "to": 4, "label": ""},
            {"from": 4, "to": 5, "label": ""},
        ],
    },
    {
        "name": "Invoice Approval Flow", "category": "Finance", "status": "active",
        "description": "Route invoices for multi-level approval based on amount",
        "nodes": [
            {"type": "trigger",   "label": "Invoice Submitted",      "x": 80,   "y": 110},
            {"type": "condition", "label": "Amount > $5,000?",        "x": 300,  "y": 110,
             "config": {"true_branch": "Yes", "false_branch": "No"}},
            {"type": "approval",  "label": "Senior Manager Approval", "x": 520,  "y": 45},
            {"type": "approval",  "label": "Team Lead Approval",      "x": 520,  "y": 175},
            {"type": "action",    "label": "Process Payment",         "x": 740,  "y": 110,
             "config": {"agent_name": "Finance Recovery Agent",
                        "task_description": "Process the approved invoice payment and update financial records."}},
            {"type": "notify",    "label": "Notify Finance Team",     "x": 960,  "y": 110,
             "config": {"channel": "slack", "message": "Invoice processed and payment completed."}},
            {"type": "end",       "label": "Done",                    "x": 1160, "y": 110},
        ],
        "edges": [
            {"from": 0, "to": 1, "label": ""},
            {"from": 1, "to": 2, "label": "Yes"},
            {"from": 1, "to": 3, "label": "No"},
            {"from": 2, "to": 4, "label": ""},
            {"from": 3, "to": 4, "label": ""},
            {"from": 4, "to": 5, "label": ""},
            {"from": 5, "to": 6, "label": ""},
        ],
    },
    {
        "name": "Ticket Escalation", "category": "Support", "status": "active",
        "description": "Auto-escalate unresolved support tickets after time thresholds",
        "nodes": [
            {"type": "trigger",   "label": "Ticket Created",      "x": 80,   "y": 110},
            {"type": "delay",     "label": "Wait 4 Hours",        "x": 280,  "y": 110,
             "config": {"delay_seconds": 14400}},
            {"type": "condition", "label": "Still Open?",         "x": 480,  "y": 110,
             "config": {"true_branch": "Yes", "false_branch": "No"}},
            {"type": "action",    "label": "Escalate to L2",      "x": 680,  "y": 50,
             "config": {"agent_name": "Customer Support Agent",
                        "task_description": "Escalate this ticket to the L2 support team and update priority."}},
            {"type": "end",       "label": "Close (Resolved)",    "x": 680,  "y": 170},
            {"type": "notify",    "label": "Alert Support Lead",  "x": 880,  "y": 50,
             "config": {"channel": "slack",
                        "message": "Ticket escalated to L2. Please review urgently."}},
            {"type": "end",       "label": "Done",                "x": 1060, "y": 50},
        ],
        "edges": [
            {"from": 0, "to": 1, "label": ""},
            {"from": 1, "to": 2, "label": ""},
            {"from": 2, "to": 3, "label": "Yes"},
            {"from": 2, "to": 4, "label": "No"},
            {"from": 3, "to": 5, "label": ""},
            {"from": 5, "to": 6, "label": ""},
        ],
    },
    {
        "name": "Employee Onboarding", "category": "HR", "status": "draft",
        "description": "Full onboarding workflow for new hires",
        "nodes": [
            {"type": "trigger",  "label": "New Hire Added",        "x": 80,   "y": 110},
            {"type": "action",   "label": "Create Accounts",       "x": 290,  "y": 110,
             "config": {"agent_name": "HR Operations Agent",
                        "task_description": "Create email, Slack, and system accounts for the new hire."}},
            {"type": "notify",   "label": "Send Welcome Email",    "x": 500,  "y": 60,
             "config": {"channel": "email",
                        "message": "Welcome to the team! Your accounts have been set up."}},
            {"type": "action",   "label": "Assign Buddy",          "x": 500,  "y": 160,
             "config": {"agent_name": "HR Operations Agent",
                        "task_description": "Assign an onboarding buddy to the new hire from the same department."}},
            {"type": "delay",    "label": "Wait 7 Days",           "x": 710,  "y": 110,
             "config": {"delay_seconds": 604800}},
            {"type": "approval", "label": "Manager Check-in",      "x": 910,  "y": 110},
            {"type": "end",      "label": "Onboarding Complete",   "x": 1110, "y": 110},
        ],
        "edges": [
            {"from": 0, "to": 1, "label": ""},
            {"from": 1, "to": 2, "label": ""},
            {"from": 1, "to": 3, "label": ""},
            {"from": 2, "to": 4, "label": ""},
            {"from": 3, "to": 4, "label": ""},
            {"from": 4, "to": 5, "label": ""},
            {"from": 5, "to": 6, "label": ""},
        ],
    },
]


class Command(BaseCommand):
    help = "Seed AI Agent Resources and example Workflows into the database"

    def handle(self, *args, **options):
        self._seed_agents()
        self._seed_workflows()
        self.stdout.write(self.style.SUCCESS("✓ Seeding complete"))

    def _seed_agents(self):
        from crmapp.agentic.core.models import Resource
        from crmapp.agentic.agents.models import AgentConfig

        for a in AGENTS:
            resource, created = Resource.objects.get_or_create(
                name=a["name"],
                defaults={
                    "type":      "AI Agent",
                    "status":    "idle",
                    "role":      a["role"],
                    "goal":      a["goal"],
                    "backstory": a["backstory"],
                    "tools":     a["tools"],
                    "metadata":  {"dept": a["dept"]},
                },
            )
            if created:
                AgentConfig.objects.get_or_create(
                    resource=resource,
                    defaults={
                        "llm":         "groq/llama-3.3-70b-versatile",
                        "temperature": 0.3,
                        "max_tokens":  512,
                        "dept":        a["dept"],
                        "skills":      a["tools"],
                    },
                )
                self.stdout.write(f"  + Agent: {a['name']}")
            else:
                self.stdout.write(f"  ~ Agent exists: {a['name']}")

    def _seed_workflows(self):
        from crmapp.automation.workflows.models import Workflow, WorkflowNode, WorkflowEdge

        for wf_data in WORKFLOWS:
            if Workflow.objects.filter(name=wf_data["name"]).exists():
                self.stdout.write(f"  ~ Workflow exists: {wf_data['name']}")
                continue

            wf = Workflow.objects.create(
                name        = wf_data["name"],
                category    = wf_data["category"],
                status      = wf_data["status"],
                description = wf_data["description"],
            )

            # Create nodes and keep index→node map
            node_index = {}
            for i, nd in enumerate(wf_data["nodes"]):
                node = WorkflowNode.objects.create(
                    workflow = wf,
                    type     = nd["type"],
                    label    = nd["label"],
                    x        = nd.get("x", 100 + i * 200),
                    y        = nd.get("y", 100),
                    config   = nd.get("config", {}),
                )
                node_index[i] = node

            # Create edges
            for ed in wf_data["edges"]:
                fn = node_index.get(ed["from"])
                tn = node_index.get(ed["to"])
                if fn and tn:
                    WorkflowEdge.objects.create(
                        workflow  = wf,
                        from_node = fn,
                        to_node   = tn,
                        label     = ed.get("label", ""),
                    )

            self.stdout.write(
                f"  + Workflow: {wf.name} "
                f"({len(wf_data['nodes'])} nodes, {len(wf_data['edges'])} edges)"
            )

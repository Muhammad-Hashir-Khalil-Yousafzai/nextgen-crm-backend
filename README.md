<div align="center">

# 🎨 NextGen CRM — Frontend

### The CRM That Doesn't Just Store Your Data — It Acts On It

<img src="https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black" alt="React"/>
<img src="https://img.shields.io/badge/Vite-Build_Tool-646CFF?style=for-the-badge&logo=vite&logoColor=white" alt="Vite"/>
<img src="https://img.shields.io/badge/Tailwind_CSS-3.4-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white" alt="Tailwind"/>
<img src="https://img.shields.io/badge/Recharts-Data_Viz-FF6384?style=for-the-badge" alt="Recharts"/>
<br/>
<img src="https://img.shields.io/badge/Status-Active_Development-296571?style=for-the-badge" alt="Status"/>
<img src="https://img.shields.io/badge/License-Academic_Project-8A2BE2?style=for-the-badge" alt="License"/>
<img src="https://img.shields.io/badge/Modules-8-teal?style=for-the-badge" alt="Modules"/>
<img src="https://img.shields.io/badge/Pages-81-teal?style=for-the-badge" alt="Pages"/>

<br/><br/>

<!-- MAIN SCREENSHOT — save as docs/screenshots/main-dashboard.png -->
<img src="docs/screenshots/main-dashboard.png" width="90%" alt="Main Dashboard"/>

<br/><br/>

**Type a goal in plain English. Watch AI agents plan it, assign it, and execute it — for real.**

[🔗 Backend Repo](https://github.com/Muhammad-Hashir-Khalil-Yousafzai/nextgen-crm-backend) · [🐛 Report Bug](../../issues) · [💡 Request Feature](../../issues) · [⭐ Star This Repo](../../stargazers)

</div>

<br/>

<div align="center">

### 🧭 Jump To

[Overview](#-the-problem-this-solves) · [How It Works](#-how-it-actually-works) · [Screenshots](#-see-it-in-action) · [Modules](#-modules--features) · [Tech Stack](#️-tech-stack) · [Getting Started](#-getting-started) · [Limitations](#️-known-limitations) · [Team](#-project-team)

</div>

---

## 📊 Project at a Glance

<div align="center">

| 🧩 8 Modules | 📄 81 Pages | 🤖 7 Agent Tools | 🔐 49-Entry RBAC | 📈 13 Dashboards |
|:---:|:---:|:---:|:---:|:---:|
| Dashboards → Finance → HRM | Full React SPA | Real, working tools | Fine-grained permissions | One per role |

</div>

---

## 🧭 The Problem This Solves

> Most CRMs built for small and medium-sized businesses are **reactive** — they log what already happened. They're also often **expensive**, **complex to configure**, and treat AI as a black box that spits out a prediction with zero explanation.

**NextGen CRM** takes a different approach. Built as a Final Year Project at Government Postgraduate College Mansehra (Hazara University), it reimagines the CRM as a proactive business assistant — one that can reason about goals, not just record data.

---

## ⚡ How Agenric AI Actually Works

This isn't a chatbot bolted onto a CRM. Here's the real flow, exactly as implemented:

```
1. You type:        "Follow up with all at-risk customers this week"
                              │
2. Goal Parser:      Sends your goal + live agent context to Groq's
                      Llama 3.3 70B, which returns a structured task plan
                              │
3. You review:       Every task is shown to you BEFORE execution —
                      human-in-the-loop by design, nothing runs blind
                              │
4. Agents execute:   Using 7 real tools — web search (Tavily), email
                      (Gmail SMTP), Slack alerts, live CRM read/write,
                      calendar booking, and analytics
                              │
5. You get results:  Tasks complete, CRM records update, and you see
                      exactly what happened and why
```

This is the same interaction shown live in the screenshots below — real parsed goals, real execution times, real task counts.

---

## ⚡ How Automation is Pefermored

1. User has Canvas and 6 nodes like trigger,delay,action,condtion etc

2. User make workflows by dragging and dropping those nodes and conntectiing them in a specific way

3. Click the run button and now automation is enablled

4. it also automate the emotion detection ,using signal,py, when a email is recevied.Similarly,
when a lead is added,xai explains automatically using shap lime strategy


## 📸 See It In Action

<!--
  HOW TO ADD SCREENSHOTS
  -----------------------
  1. Save your screenshot into: docs/screenshots/
  2. Name it exactly as shown in the comment above each image.
  3. That's it — the image will just appear. No HTML to fix, just drop the file in.
  4. To add a screenshot that isn't listed yet, copy this pattern:
        <img src="docs/screenshots/your-file-name.png" width="100%" alt="Title"/>
-->

<table>
<tr>
<td width="50%" align="center">

**🤝 CRM Core**
<!-- save as docs/screenshots/leads-management.png -->
<img src="docs/screenshots/leads-management.png" width="100%"/>
<br/>
Leads, contacts, deals, pipelines, and activity tracking, all managed from a single unified workspace.

</td>
<td width="50%" align="center">

**👥 HRM**
<!-- save as docs/screenshots/employees-grid.jpeg -->
<img src="docs/screenshots/employees-grid.jpeg" width="100%"/>
<br/>
Employees, departments, attendance, recruitment, and promotions handled end-to-end.

</td>
</tr>
<tr>
<td width="50%" align="center">

**🎯 Goal Parser & Agent Builder**
<!-- save as docs/screenshots/goal-parser.png -->
<img src="docs/screenshots/goal-parser.png" width="100%"/>
<br/>
Build custom AI agents and drive goal-driven task execution from plain-English objectives.

</td>
<td width="50%" align="center">

**😐 Emotion Detection**
<!-- save as docs/screenshots/emotion-detection.png -->
<img src="docs/screenshots/emotion-detection.png" width="100%"/>
<br/>
Detects customer emotion directly from email content to give teams sentiment context.

</td>
</tr>
<tr>
<td width="50%" align="center">

**🧠 Explainable AI (XAI)**
<!-- save as docs/screenshots/explainable-ai-xai.png -->
<img src="docs/screenshots/explainable-ai-xai.png" width="100%"/>
<br/>
Lead scoring via XGBoost explained with SHAP TreeExplainer, and deal outcome prediction via Random Forest explained with LIME.

</td>
<td width="50%" align="center">

**🔀 Workflow Builder**
<!-- save as docs/screenshots/workflow-builder.png -->
<img src="docs/screenshots/workflow-builder.png" width="100%"/>
<br/>
Build workflows on a drag-and-drop canvas that execute tasks according to the defined logic.

</td>
</tr>
<tr>
<td width="50%" align="center">

**🔐 Role-Based Access**
<!-- save as docs/screenshots/roles-permissions.png -->
<img src="docs/screenshots/roles-permissions.png" width="100%"/>
<br/>
Superadmin assigns access rights to employees based on role, backed by a 49-entry permission matrix.

</td>
<td width="50%" align="center">

**🧩 Other Integrated Modules**
<!-- save as docs/screenshots/finance-dashboard.jpeg -->
<img src="docs/screenshots/finance-dashboard.jpeg" width="100%"/>
<br/>
Finance & Accounting, Analytics, and System & Security modules, all integrated into one platform.

</td>
</tr>
</table>

> 📌 The full, module-by-module screenshot gallery lives below in [Modules & Features](#-modules--features) — every submodule has its own preview.

---

## 📦 Modules & Features

NextGen CRM is organized into **8 core modules**, each broken into focused submodules — and every single one gets its own screenshot below. Click a module to expand its gallery.

### 📑 Table of Contents

1. [Dashboards](#1--dashboards-13)
2. [CRM Operations](#2--crm-operations)
3. [Artificial Intelligence](#3--artificial-intelligence)
4. [Agentic AI & Automation](#4--agentic-ai--automation)
5. [Analytics](#5--analytics)
6. [HRM](#6--hrm)
7. [Finance & Accounting](#7--finance--accounting)
8. [Security & System](#8--security--system)

---

### 1. 📊 Dashboards (13)

Every role gets a dashboard tailored to what it actually needs to see — no digging through menus to find the numbers that matter.

<details open>
<summary><strong>🖼️ Show / hide Dashboards gallery</strong></summary>
<br/>

<table>
<tr>
<td width="33%" align="center">

**Main Dashboard**
<br/><sub>Company-wide snapshot — the first screen after login</sub>
<!-- save as docs/screenshots/main-dashboard.png -->
<img src="docs/screenshots/main-dashboard.png" width="100%"/>

</td>
<td width="33%" align="center">

**Employee Dashboard**
<br/><sub>Personal view: tasks, attendance, leave balance, payslips</sub>
<!-- save as docs/screenshots/employee-dashboard.png -->
<img src="docs/screenshots/employee-dashboard.png" width="100%"/>

</td>
<td width="33%" align="center">

**Super Admin Dashboard**
<br/><sub>System-wide control center for the top-level administrator</sub>
<!-- save as docs/screenshots/super-admin-dashboard.png -->
<img src="docs/screenshots/super-admin-dashboard.png" width="100%"/>

</td>
</tr>
<tr>
<td width="33%" align="center">

**Admin Dashboard**
<br/><sub>Day-to-day administrative oversight across modules</sub>
<!-- save as docs/screenshots/admin-dashboard.png -->
<img src="docs/screenshots/admin-dashboard.png" width="100%"/>

</td>
<td width="33%" align="center">

**HR Dashboard**
<br/><sub>Headcount, attendance trends, open roles, pending reviews</sub>
<!-- save as docs/screenshots/hr-dashboard.png -->
<img src="docs/screenshots/hr-dashboard.png" width="100%"/>

</td>
<td width="33%" align="center">

**Sales Dashboard**
<br/><sub>Pipeline health, quota tracking, deal velocity</sub>
<!-- save as docs/screenshots/sales-dashboard.png -->
<img src="docs/screenshots/sales-dashboard.png" width="100%"/>

</td>
</tr>
<tr>
<td width="33%" align="center">

**Finance Dashboard**
<br/><sub>Cash position, receivables/payables, burn rate</sub>
<!-- save as docs/screenshots/finance-dashboard.jpeg -->
<img src="docs/screenshots/finance-dashboard.jpeg" width="100%"/>

</td>
<td width="33%" align="center">

**Operations Dashboard**
<br/><sub>Process throughput and operational bottlenecks</sub>
<!-- save as docs/screenshots/operations-dashboard.png -->
<img src="docs/screenshots/operations-dashboard.png" width="100%"/>

</td>
<td width="33%" align="center">

**Marketing Dashboard**
<br/><sub>Campaign performance and lead-source breakdown</sub>
<!-- save as docs/screenshots/marketing-dashboard.png -->
<img src="docs/screenshots/marketing-dashboard.png" width="100%"/>

</td>
</tr>
<tr>
<td width="33%" align="center">

**CRM Dashboard**
<br/><sub>Unified view of leads, contacts, and deals in motion</sub>
<!-- save as docs/screenshots/crm-dashboard.png -->
<img src="docs/screenshots/crm-dashboard.png" width="100%"/>

</td>
<td width="33%" align="center">

**Customer Support Dashboard**
<br/><sub>Ticket volume, SLA compliance, resolution times</sub>
<!-- save as docs/screenshots/customer-support-dashboard.png -->
<img src="docs/screenshots/customer-support-dashboard.png" width="100%"/>

</td>
<td width="33%" align="center">

**Analytics Dashboard**
<br/><sub>Cross-module BI rollup for decision-makers</sub>
<!-- save as docs/screenshots/analytics-dashboard.png -->
<img src="docs/screenshots/analytics-dashboard.png" width="100%"/>

</td>
</tr>
<tr>
<td width="33%" align="center">

**AI Insights Dashboard**
<br/><sub>Model outputs, predictions, and AI-generated recommendations in one place</sub>
<!-- save as docs/screenshots/ai-insights-dashboard.png -->
<img src="docs/screenshots/ai-insights-dashboard.png" width="100%"/>

</td>
<td width="33%"></td>
<td width="33%"></td>
</tr>
</table>

</details>

---

### 2. 🤝 CRM Operations

The day-to-day engine for managing relationships and revenue.

<details open>
<summary><strong>🖼️ Show / hide CRM Operations gallery</strong></summary>
<br/>

<table>
<tr>
<td width="33%" align="center">

**Leads**
<br/><sub>Capture, qualify, and score incoming prospects</sub>
<!-- save as docs/screenshots/leads-management.png -->
<img src="docs/screenshots/leads-management.png" width="100%"/>

</td>
<td width="33%" align="center">

**Contacts**
<br/><sub>One record per person, linked across every deal and ticket</sub>
<!-- save as docs/screenshots/contacts.jpeg -->
<img src="docs/screenshots/contacts.jpeg" width="100%"/>

</td>
<td width="33%" align="center">

**Companies**
<br/><sub>The account-level view sitting above individual contacts</sub>
<!-- save as docs/screenshots/companies.jpeg -->
<img src="docs/screenshots/companies.jpeg" width="100%"/>

</td>
</tr>
<tr>
<td width="33%" align="center">

**Deals**
<br/><sub>Kanban-style deal tracking from open to closed-won/lost</sub>
<!-- save as docs/screenshots/deals-board.png -->
<img src="docs/screenshots/deals-board.png" width="100%"/>

</td>
<td width="33%" align="center">

**Pipeline**
<br/><sub>Configurable stage-by-stage visualization of everything in flight</sub>
<!-- save as docs/screenshots/pipeline.png -->
<img src="docs/screenshots/pipeline.png" width="100%"/>

</td>
<td width="33%" align="center">

**Activity**
<br/><sub>A timeline of every call, email, meeting, and note tied to a record</sub>
<!-- save as docs/screenshots/activity.png -->
<img src="docs/screenshots/activity.png" width="100%"/>

</td>
</tr>
<tr>
<td width="33%" align="center">

**Follow-ups & Reminders**
<br/><sub>Never let a warm lead go cold</sub>
<!-- save as docs/screenshots/follow-ups.jpeg -->
<img src="docs/screenshots/follow-ups.jpeg" width="100%"/>

</td>
<td width="33%" align="center">

**Contracts Management**
<br/><sub>Store, track, and manage customer contracts and renewal dates</sub>
<!-- save as docs/screenshots/contracts-management.png -->
<img src="docs/screenshots/contracts-management.png" width="100%"/>

</td>
<td width="33%" align="center">

**Customer Support Tickets**
<br/><sub>SLA-aware ticketing tied directly to the customer record</sub>
<!-- save as docs/screenshots/support-tickets.png -->
<img src="docs/screenshots/support-tickets.png" width="100%"/>

</td>
</tr>
<tr>
<td width="33%" align="center">

**Feedback & Surveys**
<br/><sub>Capture NPS and satisfaction data straight from customers</sub>
<!-- save as docs/screenshots/feedback-surveys.png -->
<img src="docs/screenshots/feedback-surveys.png" width="100%"/>

</td>
<td width="33%"></td>
<td width="33%"></td>
</tr>
</table>

</details>

---

### 3. 🧠 Artificial Intelligence

The intelligence layer that makes the CRM proactive instead of reactive — **fully implemented and working**, not placeholder pages.

<details open>
<summary><strong>🖼️ Show / hide Artificial Intelligence gallery</strong></summary>
<br/>

<table>
<tr>
<td width="33%" align="center">

**AI Recommendation Engine**
<br/><sub>Surfaces next-best-actions — who to follow up with, which deal is at risk</sub>
<!-- save as docs/screenshots/ai-recommendation-engine.png -->
<img src="docs/screenshots/ai-recommendation-engine.png" width="100%"/>

</td>
<td width="33%" align="center">

**Emotion Detection System**
<br/><sub>Analyzes customer interactions to flag sentiment and tone in real time</sub>
<!-- save as docs/screenshots/emotion-detection.png -->
<img src="docs/screenshots/emotion-detection.png" width="100%"/>

</td>
<td width="33%" align="center">

**Explainable AI (XAI)**
<br/><sub>Every AI output ships with a human-readable "why" — never a black box</sub>
<!-- save as docs/screenshots/explainable-ai-xai.png -->
<img src="docs/screenshots/explainable-ai-xai.png" width="100%"/>

</td>
</tr>
</table>

</details>

---

### 4. 🤖 Agentic AI & Automation

This is the module that sets NextGen CRM apart from a traditional record-keeping system — **the Workflow Builder is fully functional**, from design canvas to execution.

<details open>
<summary><strong>🖼️ Show / hide Agentic AI & Automation gallery</strong></summary>
<br/>

<table>
<tr>
<td width="33%" align="center">

**Workflow Builder**
<br/><sub>Visual, drag-and-drop canvas — workflows built here run end-to-end</sub>
<!-- save as docs/screenshots/workflow-builder.png -->
<img src="docs/screenshots/workflow-builder.png" width="100%"/>

</td>
<td width="33%" align="center">

**Autonomous Agent Manager**
<br/><sub>Define agent roles, goals, backstories, and tool access</sub>
<!-- save as docs/screenshots/agent-builder.png -->
<img src="docs/screenshots/agent-builder.png" width="100%"/>

</td>
<td width="33%" align="center">

**Task Planning Engine**
<br/><sub>Plain-English goal → structured, reviewable task plan</sub>
<!-- save as docs/screenshots/goal-parser.png -->
<img src="docs/screenshots/goal-parser.png" width="100%"/>

</td>
</tr>
<tr>
<td width="33%" align="center">

**Agent Activity Monitoring**
<br/><sub>Live view of what every agent is doing, right now</sub>
<!-- save as docs/screenshots/agent-monitoring.png -->
<img src="docs/screenshots/agent-monitoring.png" width="100%"/>

</td>
<td width="33%" align="center">

**Agent Performance Analytics**
<br/><sub>Success rates, execution times, and task-completion trends per agent</sub>
<!-- save as docs/screenshots/agent-performance-analytics.png -->
<img src="docs/screenshots/agent-performance-analytics.png" width="100%"/>

</td>
<td width="33%"></td>
</tr>
</table>

</details>

---

### 5. 📈 Analytics

Turning raw activity across every module into decisions.

<details open>
<summary><strong>🖼️ Show / hide Analytics gallery</strong></summary>
<br/>

<table>
<tr>
<td width="33%" align="center">

**Data Integration & ETL Management**
<br/><sub>Pipelines that pull, clean, and normalize data from across the system</sub>
<!-- save as docs/screenshots/data-integration-etl.png -->
<img src="docs/screenshots/data-integration-etl.png" width="100%"/>

</td>
<td width="33%" align="center">

**Business Intelligence**
<br/><sub>Cross-functional reporting for leadership</sub>
<!-- save as docs/screenshots/business-intelligence.png -->
<img src="docs/screenshots/business-intelligence.png" width="100%"/>

</td>
<td width="33%" align="center">

**KPI & Dashboard Management**
<br/><sub>Define and track the metrics that matter to your business</sub>
<!-- save as docs/screenshots/kpi-dashboard-management.png -->
<img src="docs/screenshots/kpi-dashboard-management.png" width="100%"/>

</td>
</tr>
<tr>
<td width="33%" align="center">

**Sales Analytics**
<br/><sub>Pipeline velocity, win rates, rep performance</sub>
<!-- save as docs/screenshots/sales-analytics.jpeg -->
<img src="docs/screenshots/sales-analytics.jpeg" width="100%"/>

</td>
<td width="33%" align="center">

**Customer Analytics**
<br/><sub>Retention, churn risk, lifetime value</sub>
<!-- save as docs/screenshots/customer-analytics.png -->
<img src="docs/screenshots/customer-analytics.png" width="100%"/>

</td>
<td width="33%" align="center">

**Marketing Analytics**
<br/><sub>Campaign ROI and lead-source attribution</sub>
<!-- save as docs/screenshots/marketing-analytics.png -->
<img src="docs/screenshots/marketing-analytics.png" width="100%"/>

</td>
</tr>
<tr>
<td width="33%" align="center">

**Operational Analytics**
<br/><sub>Process efficiency and throughput</sub>
<!-- save as docs/screenshots/operational-analytics.png -->
<img src="docs/screenshots/operational-analytics.png" width="100%"/>

</td>
<td width="33%" align="center">

**Predictive Analytics & Forecasting**
<br/><sub>Forward-looking projections built on historical trends</sub>
<!-- save as docs/screenshots/predictive-analytics-forecasting.png -->
<img src="docs/screenshots/predictive-analytics-forecasting.png" width="100%"/>

</td>
<td width="33%" align="center">

**Model Monitoring & AI Analytics**
<br/><sub>Tracks the health and accuracy of the AI models underneath the CRM</sub>
<!-- save as docs/screenshots/model-monitoring-ai-analytics.png -->
<img src="docs/screenshots/model-monitoring-ai-analytics.png" width="100%"/>

</td>
</tr>
</table>

</details>

---

### 6. 👥 HRM

A full employee lifecycle, from job posting to offboarding.

<details open>
<summary><strong>🖼️ Show / hide HRM gallery</strong></summary>
<br/>

<table>
<tr>
<td width="33%" align="center">

**Employees**
<br/><sub>The master employee record</sub>
<!-- save as docs/screenshots/employees-grid.jpeg -->
<img src="docs/screenshots/employees-grid.jpeg" width="100%"/>

</td>
<td width="33%" align="center">

**Departments**
<br/><sub>Organizational structure and team grouping</sub>
<!-- save as docs/screenshots/departments.png -->
<img src="docs/screenshots/departments.png" width="100%"/>

</td>
<td width="33%" align="center">

**Designations**
<br/><sub>Job titles and role hierarchy</sub>
<!-- save as docs/screenshots/designations.png -->
<img src="docs/screenshots/designations.png" width="100%"/>

</td>
</tr>
<tr>
<td width="33%" align="center">

**Recruitment — Jobs Post**
<br/><sub>Publish and manage open roles</sub>
<!-- save as docs/screenshots/recruitment-jobs.jpeg -->
<img src="docs/screenshots/recruitment-jobs.jpeg" width="100%"/>

</td>
<td width="33%" align="center">

**Recruitment — Candidates**
<br/><sub>Track applicants through the hiring pipeline</sub>
<!-- save as docs/screenshots/candidates.png -->
<img src="docs/screenshots/candidates.png" width="100%"/>

</td>
<td width="33%" align="center">

**Attendance**
<br/><sub>Company-wide attendance tracking</sub>
<!-- save as docs/screenshots/attendance.jpeg -->
<img src="docs/screenshots/attendance.jpeg" width="100%"/>

</td>
</tr>
<tr>
<td width="33%" align="center">

**Employee Attendance**
<br/><sub>Individual attendance records</sub>
<!-- save as docs/screenshots/employee-detail.jpeg -->
<img src="docs/screenshots/employee-detail.jpeg" width="100%"/>

</td>
<td width="33%" align="center">

**Leaves**
<br/><sub>Leave requests, balances, and approvals</sub>
<!-- save as docs/screenshots/leave-management.jpeg -->
<img src="docs/screenshots/leave-management.jpeg" width="100%"/>

</td>
<td width="33%" align="center">

**Performance Reviews**
<br/><sub>Structured, recurring evaluation cycles</sub>
<!-- save as docs/screenshots/performance-reviews.png -->
<img src="docs/screenshots/performance-reviews.png" width="100%"/>

</td>
</tr>
<tr>
<td width="33%" align="center">

**Promotions**
<br/><sub>Track role and compensation changes</sub>
<!-- save as docs/screenshots/promotions.png -->
<img src="docs/screenshots/promotions.png" width="100%"/>

</td>
<td width="33%" align="center">

**Terminations**
<br/><sub>Manage involuntary offboarding with proper record-keeping</sub>
<!-- save as docs/screenshots/terminations.png -->
<img src="docs/screenshots/terminations.png" width="100%"/>

</td>
<td width="33%" align="center">

**Resignations**
<br/><sub>Manage voluntary offboarding end-to-end</sub>
<!-- save as docs/screenshots/resignations.png -->
<img src="docs/screenshots/resignations.png" width="100%"/>

</td>
</tr>
</table>

</details>

---

### 7. 💰 Finance & Accounting

A proper double-entry accounting backbone, not a bolted-on expense tracker.

<details open>
<summary><strong>🖼️ Show / hide Finance & Accounting gallery</strong></summary>
<br/>

<table>
<tr>
<td width="33%" align="center">

**Chart Of Accounts**
<br/><sub>The foundational structure every transaction maps to</sub>
<!-- save as docs/screenshots/chart-of-accounts.png -->
<img src="docs/screenshots/chart-of-accounts.png" width="100%"/>

</td>
<td width="33%" align="center">

**General Ledger**
<br/><sub>The system of record for all financial entries</sub>
<!-- save as docs/screenshots/general-ledger.png -->
<img src="docs/screenshots/general-ledger.png" width="100%"/>

</td>
<td width="33%" align="center">

**Accounts Payables**
<br/><sub>What the business owes, and when it's due</sub>
<!-- save as docs/screenshots/accounts-payables.png -->
<img src="docs/screenshots/accounts-payables.png" width="100%"/>

</td>
</tr>
<tr>
<td width="33%" align="center">

**Accounts Receivables**
<br/><sub>What's owed to the business, and aging on outstanding invoices</sub>
<!-- save as docs/screenshots/accounts-receivables.png -->
<img src="docs/screenshots/accounts-receivables.png" width="100%"/>

</td>
<td width="33%" align="center">

**Cash & Bank Management**
<br/><sub>Reconciliation and cash position tracking</sub>
<!-- save as docs/screenshots/cash-bank-management.png -->
<img src="docs/screenshots/cash-bank-management.png" width="100%"/>

</td>
<td width="33%" align="center">

**Invoice & Billing Management**
<br/><sub>Generate, send, and track invoices</sub>
<!-- save as docs/screenshots/invoice-billing-management.png -->
<img src="docs/screenshots/invoice-billing-management.png" width="100%"/>

</td>
</tr>
<tr>
<td width="33%" align="center">

**Expense Management**
<br/><sub>Capture and categorize business spend</sub>
<!-- save as docs/screenshots/expense-management.png -->
<img src="docs/screenshots/expense-management.png" width="100%"/>

</td>
<td width="33%" align="center">

**Payroll**
<br/><sub>Employee compensation processing, tied directly into HRM</sub>
<!-- save as docs/screenshots/payroll.jpeg -->
<img src="docs/screenshots/payroll.jpeg" width="100%"/>

</td>
<td width="33%" align="center">

**Asset Management**
<br/><sub>Track fixed assets and depreciation</sub>
<!-- save as docs/screenshots/asset-management.png -->
<img src="docs/screenshots/asset-management.png" width="100%"/>

</td>
</tr>
<tr>
<td width="33%" align="center">

**Financial Statements — Profit & Loss**
<br/><sub>Revenue vs. expenses over a period</sub>
<!-- save as docs/screenshots/profit-loss.png -->
<img src="docs/screenshots/profit-loss.png" width="100%"/>

</td>
<td width="33%" align="center">

**Financial Statements — Balance Sheet**
<br/><sub>Assets, liabilities, and equity at a point in time</sub>
<!-- save as docs/screenshots/balance-sheet.png -->
<img src="docs/screenshots/balance-sheet.png" width="100%"/>

</td>
<td width="33%" align="center">

**Financial Statements — Cash Flow**
<br/><sub>How cash moves in and out of the business</sub>
<!-- save as docs/screenshots/cash-flow.png -->
<img src="docs/screenshots/cash-flow.png" width="100%"/>

</td>
</tr>
</table>

</details>

---

### 8. 🔐 Security & System

The guardrails that keep everything above safe and auditable.

<details open>
<summary><strong>🖼️ Show / hide Security & System gallery</strong></summary>
<br/>

<table>
<tr>
<td width="33%" align="center">

**Roles & Permissions**
<br/><sub>A 49-entry, fine-grained RBAC permission matrix</sub>
<!-- save as docs/screenshots/roles-permissions.png -->
<img src="docs/screenshots/roles-permissions.png" width="100%"/>

</td>
<td width="33%" align="center">

**User Management**
<br/><sub>Provision, deactivate, and manage user accounts</sub>
<!-- save as docs/screenshots/user-management.jpeg -->
<img src="docs/screenshots/user-management.jpeg" width="100%"/>

</td>
<td width="33%" align="center">

**Audit Logs & Activity Tracking**
<br/><sub>An immutable, append-only trail of who did what and when</sub>
<!-- save as docs/screenshots/audit-logs.png -->
<img src="docs/screenshots/audit-logs.png" width="100%"/>

</td>
</tr>
<tr>
<td width="33%" align="center">

**Authentication Management**
<br/><sub>JWT-based auth with automatic silent token refresh</sub>
<!-- save as docs/screenshots/login-screen.jpeg -->
<img src="docs/screenshots/login-screen.jpeg" width="100%"/>

</td>
<td width="33%"></td>
<td width="33%"></td>
</tr>
</table>

</details>

> 📌 Every screenshot above is from the real, running system — documented in Chapter 7 of the project thesis. Nothing here is a mockup.

---

## 🎨 Design System

<div align="center">

| Token | Value |
|:---:|:---:|
| 🎨 Primary Color | `#296571` (teal) |
| 🔤 Heading Font | Sora |
| 💻 Monospace Font | JetBrains Mono |
| 🌗 Theming | Full light/dark mode across every component |

</div>

---

## 🛠️ Tech Stack

<div align="center">

| Layer | Technology |
|:---:|:---:|
| **Framework** | React 18 |
| **Build Tool** | Vite |
| **Styling** | Tailwind CSS 3.4 |
| **Charts** | Recharts |
| **Drag & Drop** | @dnd-kit |
| **HTTP Client** | Axios (JWT interceptor, auto-refresh) |

</div>

---

## ⚡ Getting Started

```bash
git clone https://github.com/Muhammad-Hashir-Khalil-Yousafzai/nextgen-crm-frontend.git
cd nextgen-crm-frontend

npm install

cp .env.example .env
# Set your API URL, e.g. REACT_APP_API_URL=http://localhost:8000

npm start
```

Runs at `http://localhost:3000`. Requires the [backend](https://github.com/Muhammad-Hashir-Khalil-Yousafzai/nextgen-crm-backend) running alongside it.

---

## 📂 Project Structure

```
src/
├── components/
│   ├── TaskPlanningEngine.jsx    # Agentic AI dashboard
│   ├── AuditLogs.jsx
│   ├── AuthManagement.jsx
│   └── AutonomousAgents.jsx
├── pages/                        # CRM, HRM, Finance, Analytics pages
├── api/                          # Axios instance + JWT interceptor
└── App.jsx
```

---

## ⚠️ Known Limitations

Reported transparently, as documented in the project thesis:

- Built and tested with **synthetic data only** — not yet validated against a real business's live data
- **Supabase security** isn't hardened yet — data isn't fully locked down, so it's visible to the developer
- **Groq API** is on a free-tier key, so heavy usage may hit rate limits
- Performance can slow down under **high data volume** — not yet optimized for large-scale datasets

---

## 👤 Project Team

<div align="center">

Final Year Project — **BS Computer Science**, Government Postgraduate College Mansehra, affiliated with **Hazara University** (Session 2022–2026)

| Name |
|:---:|
| **Muhammad Hashir Khalil** |
| Muhammad Zeeshan |
| Muhammad Ibrar |

**Supervisor:** Mr. Muhammad Abid, Assistant Professor, Department of Computer Science

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-0077B5?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/muhammad-hashir-khalil-b79460259)
[![Email](https://img.shields.io/badge/Email-Contact-D14836?style=for-the-badge&logo=gmail&logoColor=white)](mailto:hashirkhalil3@gmail.com)

</div>

---

<div align="center">

**Backend repo:** [nextgen-crm-backend](https://github.com/Muhammad-Hashir-Khalil-Yousafzai/nextgen-crm-backend)

⭐ **If this project caught your interest, a star helps a lot!** ⭐

<img src="https://img.shields.io/badge/Made%20with-%E2%9D%A4-red?style=for-the-badge" alt="Made with love"/>

</div>

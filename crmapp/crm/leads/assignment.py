"""
assignment.py
─────────────
Lead Assignment Engine — Hybrid System
Logic:
    1. Hot lead  (score >= 70) → Senior Agent (least busy among seniors)
    2. Warm lead (score 40-69) → Least busy agent (any team)
    3. Cold lead (score < 40)  → Round robin (outbound team)

Sales Reps Config — apne real agents yahan dalo
"""

import logging

logger = logging.getLogger(__name__)

# ── Sales Agents Config ───────────────────────────────────────────────────────
# Yahan apne actual sales reps ke naam daalo
SENIOR_AGENTS = [
    'Ali Khan',
    'Sara Ahmed',
]

JUNIOR_AGENTS = [
    'Ahmed Raza',
    'Fatima Malik',
    'Hassan Siddiqui',
]

OUTBOUND_AGENTS = [
    'Usman Tariq',
    'Zara Hussain',
]

ALL_AGENTS = SENIOR_AGENTS + JUNIOR_AGENTS + OUTBOUND_AGENTS


# ── Helper: Count current leads of an agent ───────────────────────────────────
def _get_lead_count(agent_name):
    """DB se agent ka current active lead count lo"""
    from .models import Lead
    return Lead.objects.filter(
        assigned_to=agent_name,
        status__in=['not-contacted', 'contacted']
    ).count()


# ── Helper: Least busy from a pool ───────────────────────────────────────────
def _least_busy(agent_pool):
    """
    Agent pool mein se sabse kam leads wala agent return karo.
    Agar pool empty ho to fallback = first senior agent.
    """
    if not agent_pool:
        return SENIOR_AGENTS[0]

    counts = {agent: _get_lead_count(agent) for agent in agent_pool}
    logger.debug(f"[Assignment] Agent load: {counts}")
    return min(counts, key=counts.get)


# ── Helper: Round Robin Index (DB-based) ──────────────────────────────────────
def _round_robin(agent_pool):
    """
    Round robin — total leads count ke basis par next agent chuno.
    No in-memory state needed — works across restarts.
    """
    from .models import Lead
    total_leads = Lead.objects.filter(assigned_to__in=agent_pool).count()
    idx         = total_leads % len(agent_pool)
    return agent_pool[idx]


# ── Lead Classification ───────────────────────────────────────────────────────
def classify_lead(score):
    """
    Score ke basis par lead classify karo.
    Returns: 'hot' | 'warm' | 'cold'
    """
    if score >= 70:
        return 'hot'
    elif score >= 40:
        return 'warm'
    else:
        return 'cold'


# ── Main Assignment Function ──────────────────────────────────────────────────
def assign_lead(lead_instance):
    """
    Main function — call this with a Lead instance.
    
    Logic:
      Hot  → least busy SENIOR agent
      Warm → least busy ANY agent
      Cold → round robin OUTBOUND team
    
    Returns: agent name (str)
    """
    score      = getattr(lead_instance, 'score', 0) or 0
    lead_type  = classify_lead(score)
    lead_name  = getattr(lead_instance, 'name', 'Unknown')

    logger.info(f"[Assignment] Lead: '{lead_name}' | Score: {score} | Type: {lead_type}")

    if lead_type == 'hot':
        agent = _least_busy(SENIOR_AGENTS)
        logger.info(f"[Assignment] HOT → Senior Agent: {agent}")

    elif lead_type == 'warm':
        agent = _least_busy(ALL_AGENTS)
        logger.info(f"[Assignment] WARM → Least Busy: {agent}")

    else:  # cold
        if OUTBOUND_AGENTS:
            agent = _round_robin(OUTBOUND_AGENTS)
        else:
            agent = _round_robin(ALL_AGENTS)
        logger.info(f"[Assignment] COLD → Round Robin: {agent}")

    return agent


# ── Priority based on score + value ──────────────────────────────────────────
def compute_priority(score, value=0):
    """
    Lead priority calculate karo.
    High value + high score = high priority
    Returns: 'high' | 'medium' | 'low'
    """
    value = float(value or 0)

    if score >= 70 or value >= 10000:
        return 'high'
    elif score >= 40 or value >= 3000:
        return 'medium'
    else:
        return 'low'


# ── Follow-up timing based on priority ───────────────────────────────────────
def get_followup_hours(priority):
    """
    Priority ke basis par followup kitne ghante mein karna hai.
    Returns: int (hours)
    """
    return {
        'high':   2,    # 2 ghante mein call karo
        'medium': 24,   # 1 din mein
        'low':    48,   # 2 din mein
    }.get(priority, 24)
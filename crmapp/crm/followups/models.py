from django.db import models
from django.contrib.auth.models import User


class FollowUp(models.Model):
    """
    Scheduled follow-up / reminder item.

    Maps 1-to-1 with every field the frontend uses:
      title, description, type, priority, status,
      due_date, reminder_time, recurring_*, notes, tags,
      assigned_to — plus FK refs to Contact, Deal, Activity.

    Recurring
    ─────────
    Rather than a nested JSON object (which is opaque to queries),
    recurring config is stored as three flat columns:
      recurring_enabled  — bool toggle
      recurring_frequency — daily / weekly / monthly
      recurring_interval  — every N periods (default 1)
    The serializer re-assembles them as { enabled, frequency, interval }
    so the frontend receives the exact shape it expects.
    """

    # ── Type choices — matches typeIcon/typeColor maps in frontend ────────────
    TYPE_CALL     = 'call'
    TYPE_EMAIL    = 'email'
    TYPE_MEETING  = 'meeting'
    TYPE_WHATSAPP = 'whatsapp'
    TYPE_SMS      = 'sms'
    TYPE_VIDEO    = 'video'

    TYPE_CHOICES = [
        (TYPE_CALL,     'Call'),
        (TYPE_EMAIL,    'Email'),
        (TYPE_MEETING,  'Meeting'),
        (TYPE_WHATSAPP, 'WhatsApp'),
        (TYPE_SMS,      'SMS'),
        (TYPE_VIDEO,    'Video'),
    ]

    # ── Priority choices ──────────────────────────────────────────────────────
    PRIORITY_HIGH   = 'high'
    PRIORITY_MEDIUM = 'medium'
    PRIORITY_LOW    = 'low'

    PRIORITY_CHOICES = [
        (PRIORITY_HIGH,   'High'),
        (PRIORITY_MEDIUM, 'Medium'),
        (PRIORITY_LOW,    'Low'),
    ]

    # ── Status choices — matches statusColor map in frontend ──────────────────
    STATUS_PENDING   = 'pending'
    STATUS_COMPLETED = 'completed'
    STATUS_MISSED    = 'missed'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_PENDING,   'Pending'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_MISSED,    'Missed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    # ── Recurring frequency choices ───────────────────────────────────────────
    FREQ_DAILY   = 'daily'
    FREQ_WEEKLY  = 'weekly'
    FREQ_MONTHLY = 'monthly'

    FREQUENCY_CHOICES = [
        (FREQ_DAILY,   'Daily'),
        (FREQ_WEEKLY,  'Weekly'),
        (FREQ_MONTHLY, 'Monthly'),
    ]

    # ── Core fields ───────────────────────────────────────────────────────────
    title       = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    type        = models.CharField(max_length=20,  choices=TYPE_CHOICES,     default=TYPE_CALL)
    priority    = models.CharField(max_length=10,  choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM)
    status      = models.CharField(max_length=20,  choices=STATUS_CHOICES,   default=STATUS_PENDING)

    # ── Dates ─────────────────────────────────────────────────────────────────
    due_date      = models.DateTimeField()
    reminder_time = models.DateTimeField(null=True, blank=True)

    # ── Recurring (flat columns, re-assembled by serializer) ──────────────────
    recurring_enabled   = models.BooleanField(default=False)
    recurring_frequency = models.CharField(
        max_length=10, choices=FREQUENCY_CHOICES,
        default=FREQ_WEEKLY, blank=True
    )
    recurring_interval  = models.PositiveSmallIntegerField(default=1)

    # ── Assignment ────────────────────────────────────────────────────────────
    assigned_to = models.CharField(max_length=255, blank=True, default='Me')

    # ── Notes & tags ─────────────────────────────────────────────────────────
    notes = models.TextField(blank=True)
    tags  = models.JSONField(default=list, blank=True)

    # ── Polymorphic FK references ─────────────────────────────────────────────
    # All nullable — a follow-up can be standalone or linked to any entity.
    contact = models.ForeignKey(
        'crm_contacts.Contact',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='followups'
    )
    deal = models.ForeignKey(
        'crm_deals.Deal',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='followups'
    )
    activity = models.ForeignKey(
        'crm_activities.Activity',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='followups'
    )

    # ── Meta ──────────────────────────────────────────────────────────────────
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='followups_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'followups'
        ordering = ['due_date']

    def __str__(self):
        return f"[{self.type}] {self.title} — {self.status}"

    # ── Computed helpers (used by serializer read-only fields) ────────────────
    @property
    def recurring(self):
        """Re-assembles the frontend's nested { enabled, frequency, interval } shape."""
        return {
            'enabled':   self.recurring_enabled,
            'frequency': self.recurring_frequency,
            'interval':  self.recurring_interval,
        }

    @property
    def contact_name(self):
        return self.contact.name if self.contact else ''

    @property
    def contact_avatar(self):
        return self.contact.avatar if self.contact else ''

    @property
    def deal_title(self):
        return self.deal.title if self.deal else ''
from django.db import models
from django.contrib.auth.models import User
import datetime


class Ticket(models.Model):

    STATUS_CHOICES = [
        ('open',             'Open'),
        ('in_progress',      'In Progress'),
        ('waiting_customer', 'Waiting Customer'),
        ('resolved',         'Resolved'),
        ('closed',           'Closed'),
    ]

    PRIORITY_CHOICES = [
        ('low',    'Low'),
        ('medium', 'Medium'),
        ('high',   'High'),
        ('urgent', 'Urgent'),
    ]

    CATEGORY_CHOICES = [
        ('Technical Issue',   'Technical Issue'),
        ('Billing',           'Billing'),
        ('Sales Inquiry',     'Sales Inquiry'),
        ('Product Request',   'Product Request'),
        ('Complaint',         'Complaint'),
        ('Account Access',    'Account Access'),
        ('General Question',  'General Question'),
    ]

    SOURCE_CHOICES = [
        ('email', 'Email'),
        ('web',   'Web'),
        ('phone', 'Phone'),
        ('chat',  'Chat'),
        ('api',   'API'),
    ]

    # ── Core ──────────────────────────────────────────────────────
    ticket_number = models.CharField(max_length=50, unique=True, blank=True)
    subject       = models.CharField(max_length=500)
    description   = models.TextField(blank=True)
    category      = models.CharField(max_length=50,  choices=CATEGORY_CHOICES, default='Technical Issue')
    priority      = models.CharField(max_length=10,  choices=PRIORITY_CHOICES, default='medium')
    status        = models.CharField(max_length=20,  choices=STATUS_CHOICES,   default='open')
    source        = models.CharField(max_length=10,  choices=SOURCE_CHOICES,   default='web')

    # ── Relation to Contact ────────────────────────────────────────
    contact = models.ForeignKey(
        'crm_contacts.Contact',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='tickets'
    )

    # ── Customer info (denormalised for quick display) ────────────
    customer_name   = models.CharField(max_length=255, blank=True)
    customer_email  = models.EmailField(blank=True)
    customer_avatar = models.URLField(blank=True)

    # ── Assignment ────────────────────────────────────────────────
    assigned_to   = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_tickets'
    )
    assigned_name = models.CharField(max_length=255, blank=True)  # denormalised

    # ── JSON fields ───────────────────────────────────────────────
    tags = models.JSONField(default=list, blank=True)

    # ── Timestamps ────────────────────────────────────────────────
    first_response_at = models.DateTimeField(null=True, blank=True)
    resolved_at       = models.DateTimeField(null=True, blank=True)

    # ── Meta ──────────────────────────────────────────────────────
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='tickets_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tickets'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.ticket_number} — {self.subject}"

    def save(self, *args, **kwargs):
        # Auto-generate ticket number
        if not self.ticket_number:
            year  = datetime.date.today().year
            count = Ticket.objects.filter(created_at__year=year).count() + 1
            self.ticket_number = f"TCK-{year}-{str(count).zfill(4)}"

        # Denormalise contact fields
        if self.contact:
            if not self.customer_name:
                self.customer_name  = self.contact.name
            if not self.customer_email:
                self.customer_email = self.contact.email
            if not self.customer_avatar:
                self.customer_avatar = self.contact.avatar

        # Denormalise assigned agent name
        if self.assigned_to and not self.assigned_name:
            self.assigned_name = self.assigned_to.get_full_name() or self.assigned_to.username

        super().save(*args, **kwargs)

    # ── SLA rules (minutes) ───────────────────────────────────────
    SLA_RULES = {'low': 2880, 'medium': 1440, 'high': 480, 'urgent': 120}

    @property
    def sla_status(self):
        if self.status in ('resolved', 'closed'):
            return 'met'
        from django.utils import timezone
        elapsed = (timezone.now() - self.created_at).total_seconds() / 60
        limit   = self.SLA_RULES.get(self.priority, 1440)
        pct     = elapsed / limit
        if pct >= 1:    return 'breached'
        if pct >= 0.75: return 'at_risk'
        return 'ok'

    @property
    def sla_elapsed_pct(self):
        """Percentage of SLA time consumed (capped at 100)."""
        from django.utils import timezone
        elapsed = (timezone.now() - self.created_at).total_seconds() / 60
        limit   = self.SLA_RULES.get(self.priority, 1440)
        return min(100, round((elapsed / limit) * 100, 1))

    @property
    def is_unresponded(self):
        return self.first_response_at is None and self.status == 'open'


class TicketReply(models.Model):

    SENDER_TYPE_CHOICES = [
        ('agent',    'Agent'),
        ('customer', 'Customer'),
    ]

    ticket      = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='replies')
    sender_type = models.CharField(max_length=10, choices=SENDER_TYPE_CHOICES, default='agent')
    sender_name = models.CharField(max_length=255)
    avatar      = models.URLField(blank=True)
    message     = models.TextField()
    is_internal = models.BooleanField(default=False)  # internal notes hidden from customer
    created_by  = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='ticket_replies'
    )
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ticket_replies'
        ordering = ['created_at']

    def __str__(self):
        return f"Reply on {self.ticket.ticket_number} by {self.sender_name}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        # Auto-set first_response_at on the parent ticket
        ticket = self.ticket
        if (
            self.sender_type == 'agent'
            and not self.is_internal
            and ticket.first_response_at is None
        ):
            from django.utils import timezone
            ticket.first_response_at = timezone.now()
            ticket.save(update_fields=['first_response_at', 'updated_at'])

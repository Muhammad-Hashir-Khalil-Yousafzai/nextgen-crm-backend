from django.db import models
from django.contrib.auth.models import User


class Lead(models.Model):

    STATUS_CHOICES = [
        ('not-contacted', 'Not Contacted'),
        ('contacted',     'Contacted'),
        ('closed',        'Closed Won'),
        ('lost',          'Closed Lost'),
    ]
    PRIORITY_CHOICES = [
        ('high',   'High'),
        ('medium', 'Medium'),
        ('low',    'Low'),
    ]
    SOURCE_CHOICES = [
        ('Website',  'Website'),
        ('Referral', 'Referral'),
        ('Cold Call','Cold Call'),
        ('LinkedIn', 'LinkedIn'),
        ('Event',    'Event'),
        ('Other',    'Other'),
    ]
    STAGE_CHOICES = [
        ('Lead',        'Lead'),
        ('Prospecting', 'Prospecting'),
        ('Proposal',    'Proposal'),
        ('Negotiation', 'Negotiation'),
        ('Closed Won',  'Closed Won'),
        ('Closed Lost', 'Closed Lost'),
    ]

    # ── Core identity ──────────────────────────────────────────────
    name        = models.CharField(max_length=255)
    initials    = models.CharField(max_length=5, blank=True)
    email       = models.EmailField(blank=True)
    phone       = models.CharField(max_length=50, blank=True)
    location    = models.CharField(max_length=255, blank=True)

    # ── Relations ──────────────────────────────────────────────────
    contact     = models.ForeignKey(
        'crm_contacts.Contact',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='leads'
    )
    company     = models.ForeignKey(
        'crm_companies.Company',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='leads'
    )
    company_name = models.CharField(max_length=255, blank=True)   # fallback

    # ── Deal info ──────────────────────────────────────────────────
    value        = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    probability  = models.IntegerField(default=50)     # 0-100
    score        = models.IntegerField(default=0)      # computed / manual
    deal_stage   = models.CharField(max_length=50, choices=STAGE_CHOICES, default='Lead')

    # ── Classification ─────────────────────────────────────────────
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not-contacted')
    priority    = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    source      = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='Website')
    tags        = models.JSONField(default=list, blank=True)

    # ── Assignment ─────────────────────────────────────────────────
    assigned_to  = models.CharField(max_length=255, blank=True)

    # ── Activity ───────────────────────────────────────────────────
    last_contact = models.CharField(max_length=100, blank=True, default='Never')
    next_action  = models.CharField(max_length=255, blank=True)
    notes_count  = models.IntegerField(default=0)
    activities   = models.IntegerField(default=0)
    lost_reason  = models.CharField(max_length=255, blank=True)
    activity_log = models.JSONField(default=list, blank=True)

    # ── Meta ───────────────────────────────────────────────────────
    notes        = models.TextField(blank=True)
    created_by   = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='leads_created'
    )
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'leads'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} — {self.status}"

    def save(self, *args, **kwargs):
        # Auto-generate initials
        if not self.initials and self.name:
            parts = self.name.split()
            self.initials = ''.join(p[0].upper() for p in parts[:2])
        # Pull company name from FK
        if self.company and not self.company_name:
            self.company_name = self.company.name
        super().save(*args, **kwargs)

    @property
    def weighted_value(self):
        return float(self.value) * (self.probability / 100)


class LeadNote(models.Model):
    lead       = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='lead_notes')
    content    = models.TextField()
    created_by = models.CharField(max_length=255, default='User')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'lead_notes'
        ordering = ['-created_at']

    def __str__(self):
        return f"Note on {self.lead.name}"

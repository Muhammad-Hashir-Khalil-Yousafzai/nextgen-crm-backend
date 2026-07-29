from django.db import models
from django.contrib.auth.models import User


class Deal(models.Model):

    STAGE_CHOICES = [
        ('new',      'New'),
        ('prospect', 'Prospect'),
        ('proposal', 'Proposal'),
        ('won',      'Won'),
    ]

    # ── Core identity ──────────────────────────────────────────────
    title       = models.CharField(max_length=255)
    code        = models.CharField(max_length=10, blank=True)   # e.g. "WR", "MA"

    # ── Contact info (denormalised for quick display on cards) ─────
    email       = models.EmailField(blank=True)
    phone       = models.CharField(max_length=50, blank=True)
    location    = models.CharField(max_length=255, blank=True)

    # ── Relationships ──────────────────────────────────────────────
    contact = models.ForeignKey(
        'crm_contacts.Contact',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='deals'
    )
    company = models.ForeignKey(
        'crm_companies.Company',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='deals'
    )
    company_name = models.CharField(max_length=255, blank=True)  # fallback

    lead = models.ForeignKey(
        'crm_leads.Lead',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='deals'
    )

    pipeline = models.ForeignKey(
        'crm_pipeline.Pipeline',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='deals'
    )

    # ── Deal financials ────────────────────────────────────────────
    value       = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    probability = models.IntegerField(default=50)   # 0–100

    # ── Stage / classification ─────────────────────────────────────
    stage       = models.CharField(max_length=20, choices=STAGE_CHOICES, default='new')
    tags        = models.JSONField(default=list, blank=True)

    # ── Assignment ─────────────────────────────────────────────────
    assigned_to    = models.CharField(max_length=255, blank=True)
    assignee_avatar = models.URLField(blank=True)

    # ── Dates ──────────────────────────────────────────────────────
    close_date  = models.DateField(null=True, blank=True)   # "date" in frontend

    # ── Notes / activity ──────────────────────────────────────────
    notes        = models.TextField(blank=True)
    activity_log = models.JSONField(default=list, blank=True)

    # ── Meta ───────────────────────────────────────────────────────
    created_by  = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='deals_created'
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'deals'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} — {self.stage}"

    def save(self, *args, **kwargs):
        # Auto-generate code from title initials
        if not self.code and self.title:
            self.code = ''.join(w[0].upper() for w in self.title.split()[:3])
        # Sync company_name from FK
        if self.company and not self.company_name:
            self.company_name = self.company.name
        super().save(*args, **kwargs)

    @property
    def weighted_value(self):
        return float(self.value) * (self.probability / 100)

    @property
    def company_display(self):
        return self.company.name if self.company else self.company_name

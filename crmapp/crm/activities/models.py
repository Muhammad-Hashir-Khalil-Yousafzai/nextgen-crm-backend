from django.db import models
from django.contrib.auth.models import User


class Activity(models.Model):

    TYPE_CHOICES = [
        ('Meeting', 'Meeting'),
        ('Calls',   'Calls'),
        ('Tasks',   'Tasks'),
        ('Email',   'Email'),
    ]

    # ── Core fields ────────────────────────────────────────────────
    title         = models.CharField(max_length=500)
    activity_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='Meeting')

    # ── Dates ──────────────────────────────────────────────────────
    due_date      = models.DateField()
    created_date  = models.DateField(auto_now_add=True)

    # ── Owner (display name, matching the frontend `owner` field) ──
    owner         = models.CharField(max_length=255)

    # ── Optional image stored as Base64 text ──────────────────────
    # When null/blank, the frontend falls back to the type icon.
    # Base64 strings can be large; TextField has no length cap in
    # most DB backends (vs. CharField which is limited to ~65 535 B).
    owner_image   = models.TextField(
        blank=True,
        help_text=(
            "Base64-encoded image (e.g. data:image/png;base64,…). "
            "Leave empty to display the activity-type icon instead."
        )
    )

    # ── Optional FK relations ──────────────────────────────────────
    # Activities can optionally be linked to existing CRM records.
    contact = models.ForeignKey(
        'crm_contacts.Contact',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='activities'
    )
    company = models.ForeignKey(
        'crm_companies.Company',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='activities'
    )
    lead = models.ForeignKey(
        'crm_leads.Lead',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='activity_records'
    )
    deal = models.ForeignKey(
        'crm_deals.Deal',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='activitY_records'
    )

    # ── Notes ─────────────────────────────────────────────────────
    notes = models.TextField(blank=True)

    # ── Meta ──────────────────────────────────────────────────────
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='activities_created'
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'activities'
        ordering = ['-created_date', '-id']

    def __str__(self):
        return f"[{self.activity_type}] {self.title} — {self.owner}"

    @property
    def is_overdue(self):
        from datetime import date
        return self.due_date < date.today()

    @property
    def has_image(self):
        return bool(self.owner_image)

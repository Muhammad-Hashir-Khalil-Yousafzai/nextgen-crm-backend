from django.db import models
from django.contrib.auth.models import User


class Contact(models.Model):
    STATUS_CHOICES = [
        ('active',   'Active'),
        ('inactive', 'Inactive'),
    ]

    name         = models.CharField(max_length=255)
    title        = models.CharField(max_length=255, blank=True)
    email        = models.EmailField(unique=True)
    phone        = models.CharField(max_length=50, blank=True)
    location     = models.CharField(max_length=100, blank=True)

    # ── ForeignKey to Company ──────────────────────────────────────
    company = models.ForeignKey(
    'crm_companies.Company',
    on_delete=models.SET_NULL,
    null=True, blank=True,
    related_name='contacts'
)
    company_name = models.CharField(max_length=255, blank=True)   # fallback text

    rating       = models.FloatField(default=0.0)
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    avatar       = models.URLField(blank=True)
    tags         = models.JSONField(default=list, blank=True)
    last_contact = models.DateField(null=True, blank=True)
    notes        = models.TextField(blank=True)
    created_by   = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='contacts_created'
    )
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'contacts'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} — {self.email}"

    @property
    def company_display(self):
        """Returns company name from FK or fallback text field"""
        if self.company:
            return self.company.name
        return self.company_name

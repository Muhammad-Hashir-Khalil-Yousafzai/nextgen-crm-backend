from django.db import models
from django.contrib.auth.models import User


class Contract(models.Model):

    STATUS_CHOICES = [
        ('draft',            'Draft'),
        ('pending_approval', 'Pending Approval'),
        ('active',           'Active'),
        ('expired',          'Expired'),
        ('terminated',       'Terminated'),
        ('renewed',          'Renewed'),
    ]

    TYPE_CHOICES = [
        ('Sales',    'Sales'),
        ('Service',  'Service'),
        ('NDA',      'NDA'),
        ('Purchase', 'Purchase'),
        ('SLA',      'SLA'),
        ('Partner',  'Partner'),
    ]

    # ── Core ──────────────────────────────────────────────────────
    contract_number  = models.CharField(max_length=50, unique=True, blank=True)
    title            = models.CharField(max_length=500)
    contract_type    = models.CharField(max_length=20, choices=TYPE_CHOICES, default='Sales')
    status           = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    description      = models.TextField(blank=True)
    version          = models.IntegerField(default=1)

    # ── Relations ─────────────────────────────────────────────────
    contact = models.ForeignKey(
        'crm_contacts.Contact',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='contracts'
    )
    deal = models.ForeignKey(
        'crm_deals.Deal',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='contracts'
    )

    # ── Customer info (denormalised for quick display) ────────────
    customer_name    = models.CharField(max_length=255, blank=True)
    customer_email   = models.EmailField(blank=True)
    customer_company = models.CharField(max_length=255, blank=True)
    customer_avatar  = models.URLField(blank=True)

    # ── Financials ────────────────────────────────────────────────
    total_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    currency    = models.CharField(max_length=10, default='USD')

    # ── Dates ─────────────────────────────────────────────────────
    start_date             = models.DateField(null=True, blank=True)
    end_date               = models.DateField(null=True, blank=True)
    renewal_reminder_date  = models.DateField(null=True, blank=True)

    # ── JSON fields ───────────────────────────────────────────────
    tags       = models.JSONField(default=list, blank=True)
    signatures = models.JSONField(default=list, blank=True)
    audit_log  = models.JSONField(default=list, blank=True)
    versions   = models.JSONField(default=list, blank=True)
    approved_by = models.JSONField(default=list, blank=True)

    # ── Meta ──────────────────────────────────────────────────────
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='contracts_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'contracts'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.contract_number} — {self.title}"

    def save(self, *args, **kwargs):
        if not self.contract_number:
            import datetime
            year = datetime.date.today().year
            count = Contract.objects.filter(
                created_at__year=year
            ).count() + 1
            self.contract_number = f"CTR-{year}-{str(count).zfill(4)}"
        if self.contact and not self.customer_name:
            self.customer_name  = self.contact.name
            self.customer_email = self.contact.email
            self.customer_company = self.contact.company_name
        super().save(*args, **kwargs)

    @property
    def days_until_expiry(self):
        if not self.end_date:
            return None
        from datetime import date
        return (self.end_date - date.today()).days

    @property
    def renewal_urgency(self):
        d = self.days_until_expiry
        if d is None or self.status != 'active':
            return None
        if d < 0:   return 'expired'
        if d <= 30: return 'critical'
        if d <= 60: return 'warning'
        return None
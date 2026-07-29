from django.db import models
from django.conf import settings


class AccountType(models.TextChoices):
    ASSET     = "Asset",     "Asset"
    LIABILITY = "Liability", "Liability"
    EQUITY    = "Equity",    "Equity"
    REVENUE   = "Revenue",   "Revenue"
    EXPENSE   = "Expense",   "Expense"


class AccountStatus(models.TextChoices):
    ACTIVE   = "active",   "Active"
    INACTIVE = "inactive", "Inactive"


class LinkedModule(models.TextChoices):
    CASH_BANK = "Cash & Bank", "Cash & Bank"
    AR        = "AR",          "AR"
    AP        = "AP",          "AP"
    PAYROLL   = "Payroll",     "Payroll"
    ASSETS    = "Assets",      "Assets"


class Account(models.Model):
    code          = models.CharField(max_length=20, unique=True)
    name          = models.CharField(max_length=255)
    type          = models.CharField(max_length=20, choices=AccountType.choices)
    parent        = models.ForeignKey(
        "self", null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="children"
    )
    level         = models.PositiveSmallIntegerField(default=0)
    balance       = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    budget        = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    currency      = models.CharField(max_length=3, default="USD")
    status        = models.CharField(max_length=10, choices=AccountStatus.choices, default="active")
    linked_module = models.CharField(max_length=20, choices=LinkedModule.choices, null=True, blank=True)
    note          = models.TextField(blank=True, default="")
    created_by    = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="accounts_created")
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]
        verbose_name_plural = "Chart of Accounts"

    def __str__(self):
        return f"{self.code} - {self.name}"

    def get_computed_balance(self):
        """
        Balance ko posted JournalLines se directly (live) calculate karta hai,
        stored `balance` field pe depend nahi karta — isliye kabhi stale nahi hoga,
        chahe post_entry() mein kabhi koi bug/glitch aa jaye.
        """
        from django.db.models import Sum
        from crmapp.finance.ledger.models import JournalLine  # lazy import, circular import se bachne ke liye

        if self.children.exists():
            # Parent/summary account: sab leaf children ka total sum karo
            return sum(child.get_computed_balance() for child in self.children.all())

        totals = JournalLine.objects.filter(
            account=self,
            entry__status='posted'
        ).aggregate(debit_sum=Sum('debit'), credit_sum=Sum('credit'))
        debit_sum = totals['debit_sum'] or 0
        credit_sum = totals['credit_sum'] or 0
        return debit_sum - credit_sum

    @property
    def budget_utilization_pct(self):
        if not self.budget or self.budget == 0:
            return None
        return round((abs(self.get_computed_balance()) / abs(self.budget)) * 100)


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ("Created", "Created"), ("Updated", "Updated"),
        ("Activated", "Activated"), ("Deactivated", "Deactivated"),
    ]
    account   = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="audit_logs")
    action    = models.CharField(max_length=20, choices=ACTION_CHOICES)
    field     = models.CharField(max_length=100, blank=True, default="—")
    old_value = models.CharField(max_length=255, blank=True, default="—")
    new_value = models.CharField(max_length=255, blank=True, default="—")
    by        = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_entries")
    at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-at"]

    def __str__(self):
        return f"{self.action} on {self.account.code}"
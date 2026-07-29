from django.db import models
import uuid
from django.conf import settings

class ExpenseCategory(models.Model):
    name       = models.CharField(max_length=100)
    code       = models.CharField(max_length=20, unique=True)
    parent     = models.ForeignKey("self", null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="children")
    level      = models.IntegerField(default=0)
    gl_account = models.ForeignKey(
        "coa.Account", null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="expense_categories",
        help_text="Linked Chart of Accounts entry"
    )
    budget     = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    spent      = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='expense_categories_created')

    class Meta:
        ordering = ['code']
        verbose_name_plural = "Expense Categories"

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def remaining_budget(self):
        return self.budget - self.spent

    @property
    def utilization_pct(self):
        if not self.budget:
            return None
        return round((self.spent / self.budget) * 100)


class ExpenseClaim(models.Model):
    STATUS = [("draft", "Draft"), ("submitted", "Submitted"),
              ("approved", "Approved"), ("paid", "Paid"), ("flagged", "Flagged")]

    employee = models.ForeignKey(
        "crmapp.Employee", 
        on_delete=models.PROTECT, 
        related_name="expense_claims",
        to_field='id',
    )
    category   = models.ForeignKey(
        ExpenseCategory, on_delete=models.PROTECT, related_name="claims"
    )
    amount     = models.DecimalField(max_digits=12, decimal_places=2)
    date       = models.DateField()
    status     = models.CharField(max_length=15, choices=STATUS, default="draft")
    receipt    = models.FileField(upload_to="expense_receipts/", null=True, blank=True)
    notes      = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='expense_claims_created')

    def __str__(self):
        return f"Claim #{self.id} - {self.employee.name} - {self.amount}"
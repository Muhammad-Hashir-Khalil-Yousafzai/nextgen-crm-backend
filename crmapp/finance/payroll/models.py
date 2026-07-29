from django.db import models
from django.conf import settings

class PayrollRun(models.Model):
    STATUS = [("draft", "Draft"), ("approved", "Approved"), ("paid", "Paid")]
    month       = models.CharField(max_length=20)
    status      = models.CharField(max_length=15, choices=STATUS, default="draft")
    total_gross = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    total_net   = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    total_tax   = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)
    created_by  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='payroll_runs_created')

    def __str__(self):
        return f"Payroll {self.month} - {self.status}"


class PayrollLine(models.Model):
    run = models.ForeignKey(
        PayrollRun, on_delete=models.CASCADE, related_name="lines"
    )

    employee = models.ForeignKey(
        'crmapp.Employee', on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='payroll_lines'
    )

    basic      = models.DecimalField(max_digits=12, decimal_places=2)
    allowances = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax        = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_pay    = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.employee.name} - {self.run.month} - {self.net_pay}"
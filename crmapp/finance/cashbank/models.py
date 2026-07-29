from django.db import models
from django.conf import settings

class BankAccount(models.Model):
    bank_name       = models.CharField(max_length=100)
    account_number  = models.CharField(max_length=30)
    branch          = models.CharField(max_length=100, blank=True)
    currency        = models.CharField(max_length=3, default="USD")
    iban            = models.CharField(max_length=50, blank=True)
    swift           = models.CharField(max_length=20, blank=True)
    opening_balance = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    current_balance = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    status          = models.CharField(max_length=10, choices=[("active","Active"),("inactive","Inactive")], default="active")
    color           = models.CharField(max_length=10, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    created_by      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='bank_accounts_created')
    def __str__(self): return f"{self.bank_name} {self.account_number}"


class CashAccount(models.Model):
    name     = models.CharField(max_length=100)
    branch   = models.CharField(max_length=100)
    balance  = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="USD")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='cash_accounts_created')
    def __str__(self): return f"{self.name} ({self.branch})"


class Transaction(models.Model):
    TYPE = [("receipt","Receipt"),("payment","Payment"),("transfer","Transfer"),("fee","Bank Fee")]
    bank_account = models.ForeignKey(BankAccount, on_delete=models.PROTECT, related_name="transactions")
    type         = models.CharField(max_length=15, choices=TYPE)
    amount       = models.DecimalField(max_digits=16, decimal_places=2)
    date         = models.DateField()
    description  = models.CharField(max_length=255)
    method       = models.CharField(max_length=20, blank=True)
    reference    = models.CharField(max_length=50, blank=True)
    category     = models.CharField(max_length=50, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    def __str__(self): return f"{self.type} {self.amount} on {self.date}"


class Cheque(models.Model):
    STATUS = [("issued","Issued"),("deposited","Deposited"),("cleared","Cleared"),("bounced","Bounced")]
    bank_account = models.ForeignKey(BankAccount, on_delete=models.PROTECT, related_name="cheques")
    number       = models.CharField(max_length=20, unique=True)
    payee        = models.CharField(max_length=255)
    amount       = models.DecimalField(max_digits=14, decimal_places=2)
    issue_date   = models.DateField()
    due_date     = models.DateField()
    status       = models.CharField(max_length=15, choices=STATUS, default="issued")
    reference    = models.CharField(max_length=50, blank=True)
    def __str__(self): return f"{self.number} - {self.payee}"


class BankReconciliation(models.Model):
    bank_account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, related_name="reconciliations")
    date         = models.DateField()
    description  = models.CharField(max_length=255)
    system_amt   = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    bank_amt     = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    status       = models.CharField(max_length=15, choices=[("matched","Matched"),("unmatched","Unmatched")], default="unmatched")
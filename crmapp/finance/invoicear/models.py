from django.db import models
from django.conf import settings

class Customer(models.Model):
    name          = models.CharField(max_length=255)
    company       = models.CharField(max_length=255, blank=True)
    email         = models.EmailField()
    phone         = models.CharField(max_length=30, blank=True)
    credit_limit  = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    payment_terms = models.IntegerField(default=30)
    balance       = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    risk          = models.CharField(max_length=10, choices=[("Low","Low"),("Medium","Medium"),("High","High")], default="Low")
    avatar_url    = models.URLField(blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    created_by    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='customers_created')
    def __str__(self): return f"{self.name} ({self.company})"


class Invoice(models.Model):
    STATUS = [("draft","Draft"),("sent","Sent"),("paid","Paid"),
              ("partially_paid","Partially Paid"),("overdue","Overdue"),("disputed","Disputed")]
    invoice_no   = models.CharField(max_length=30, unique=True)
    customer     = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="invoices")
    amount       = models.DecimalField(max_digits=14, decimal_places=2)
    paid_amount  = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    invoice_date = models.DateField()
    due_date     = models.DateField()
    status       = models.CharField(max_length=15, choices=STATUS, default="draft")
    notes        = models.TextField(blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)
    created_by   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='invoices_created')
    @property
    def outstanding(self): return self.amount - self.paid_amount
    def __str__(self): return self.invoice_no


class InvoiceItem(models.Model):
    invoice     = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")
    description = models.CharField(max_length=255)
    qty         = models.DecimalField(max_digits=10, decimal_places=2)
    rate        = models.DecimalField(max_digits=14, decimal_places=2)
    @property
    def total(self): return self.qty * self.rate


class ARPayment(models.Model):
    METHOD = [("Bank Transfer","Bank Transfer"),("Card","Card"),("Cash","Cash"),("Online","Online")]
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="payments")
    amount  = models.DecimalField(max_digits=14, decimal_places=2)
    date    = models.DateField()
    method  = models.CharField(max_length=20, choices=METHOD)


class Dispute(models.Model):
    invoice    = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="disputes")
    reason     = models.CharField(max_length=255)
    status     = models.CharField(max_length=20, default="Open")
    note       = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
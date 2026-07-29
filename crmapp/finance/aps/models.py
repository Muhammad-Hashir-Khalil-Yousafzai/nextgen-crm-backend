from django.db import models
from django.conf import settings

class Vendor(models.Model):
    name       = models.CharField(max_length=255)
    company    = models.CharField(max_length=255, blank=True)
    email      = models.EmailField()
    phone      = models.CharField(max_length=30, blank=True)
    tax_id     = models.CharField(max_length=50, blank=True)
    address    = models.TextField(blank=True)
    terms      = models.IntegerField(default=30)
    currency   = models.CharField(max_length=3, default="USD")
    balance    = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    risk       = models.CharField(max_length=10, choices=[("Low","Low"),("Medium","Medium"),("High","High")], default="Low")
    avatar_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='vendors_created')
    def __str__(self): return self.name


class Bill(models.Model):
    STATUS = [("draft","Draft"),("pending","Pending"),("approved","Approved"),
              ("partial","Partially Paid"),("paid","Paid"),("overdue","Overdue")]
    number      = models.CharField(max_length=30, unique=True)
    vendor      = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name="bills")
    invoice_ref = models.CharField(max_length=50, blank=True)
    amount      = models.DecimalField(max_digits=14, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax         = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    bill_date   = models.DateField()
    due_date    = models.DateField()
    status      = models.CharField(max_length=15, choices=STATUS, default="draft")
    category    = models.CharField(max_length=50, blank=True)
    notes       = models.TextField(blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)
    created_by  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='bills_created')
    @property
    def outstanding(self): return self.amount - self.paid_amount
    def __str__(self): return self.number


class BillItem(models.Model):
    bill        = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name="items")
    description = models.CharField(max_length=255)
    qty         = models.DecimalField(max_digits=10, decimal_places=2)
    rate        = models.DecimalField(max_digits=14, decimal_places=2)
    @property
    def total(self): return self.qty * self.rate


class APPayment(models.Model):
    bill   = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    date   = models.DateField()
    method = models.CharField(max_length=20, choices=[
        ("Bank Transfer","Bank Transfer"),("Card","Card"),
        ("Cash","Cash"),("Online","Online"),("Cheque","Cheque")])


class BillApproval(models.Model):
    bill   = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name="approvals")
    role   = models.CharField(max_length=50)
    name   = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=[("pending","Pending"),("approved","Approved"),("rejected","Rejected")], default="pending")
    date   = models.DateField(null=True, blank=True)
    note   = models.TextField(blank=True)


class PurchaseOrder(models.Model):
    STATUS = [("open","Open"),("partial","Partial"),("matched","Matched")]
    number = models.CharField(max_length=30, unique=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name="purchase_orders")
    bill   = models.ForeignKey(Bill, null=True, blank=True, on_delete=models.SET_NULL, related_name="purchase_orders")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    date   = models.DateField()
    status = models.CharField(max_length=15, choices=STATUS, default="open")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='purchase_orders_created')
    def __str__(self): return self.number
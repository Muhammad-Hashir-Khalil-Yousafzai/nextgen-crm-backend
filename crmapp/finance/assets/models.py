from django.db import models
from django.conf import settings

class Asset(models.Model):
    CATEGORY = [("IT", "IT"), ("Office", "Office"), ("Vehicle", "Vehicle"),
                ("Machinery", "Machinery"), ("License", "License")]
    STATUS   = [("available", "Available"), ("assigned", "Assigned"),
                ("maintenance", "Maintenance"), ("disposed", "Disposed")]

    asset_tag     = models.CharField(max_length=30, unique=True)
    name          = models.CharField(max_length=255)
    category      = models.CharField(max_length=20, choices=CATEGORY)
    serial_number = models.CharField(max_length=100, blank=True)
    purchase_date = models.DateField()
    purchase_cost = models.DecimalField(max_digits=14, decimal_places=2)
    vendor_name   = models.CharField(max_length=255, blank=True)
    status        = models.CharField(max_length=15, choices=STATUS, default="available")
    notes         = models.TextField(blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)
    created_by    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='finance_assets_created')

    def __str__(self):
        return f"{self.asset_tag} - {self.name}"


class AssetAssignment(models.Model):
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="assignments")

    employee = models.ForeignKey(
        'crmapp.Employee', on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='asset_assignments'
    )

    assigned_date = models.DateField()
    returned_date = models.DateField(null=True, blank=True)

    @property
    def is_active(self):
        return self.returned_date is None

    @property
    def department(self):
        return self.employee.department.name if self.employee.department else None

    def __str__(self):
        return f"{self.asset.asset_tag} → {self.employee.full_name}"


class AssetMaintenance(models.Model):
    asset        = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="maintenance_history")
    type         = models.CharField(max_length=20, choices=[("Preventive", "Preventive"), ("Repair", "Repair")])
    cost         = models.DecimalField(max_digits=10, decimal_places=2)
    performed_by = models.CharField(max_length=100)
    date         = models.DateField()
    next_due     = models.DateField(null=True, blank=True)
    notes        = models.TextField(blank=True)
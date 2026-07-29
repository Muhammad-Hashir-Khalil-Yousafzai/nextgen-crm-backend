from .models import Asset, AssetAssignment, AssetMaintenance

def create_asset(data, user=None):
    return Asset.objects.create(**data, created_by=user)

def assign_asset(asset, employee, assigned_date):
    asset.assignments.filter(returned_date__isnull=True).update(returned_date=assigned_date)
    assignment = AssetAssignment.objects.create(asset=asset, employee=employee, assigned_date=assigned_date)
    asset.status = "assigned"
    asset.save(update_fields=["status", "updated_at"])
    return assignment

def return_asset(asset, returned_date):
    asset.assignments.filter(returned_date__isnull=True).update(returned_date=returned_date)
    asset.status = "available"
    asset.save(update_fields=["status", "updated_at"])
    return asset

def log_maintenance(asset, mtype, cost, performed_by, date, next_due=None, notes=""):
    if mtype == "Repair":
        asset.status = "maintenance"
        asset.save(update_fields=["status", "updated_at"])
    return AssetMaintenance.objects.create(asset=asset, type=mtype, cost=cost, performed_by=performed_by, date=date, next_due=next_due, notes=notes)
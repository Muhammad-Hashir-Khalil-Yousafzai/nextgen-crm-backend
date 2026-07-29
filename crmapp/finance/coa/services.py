from .models import Account, AuditLog

def _log(account, action, field="Account Details", old_val="None", new_val="—", user=None):
    AuditLog.objects.create(
        account=account, action=action, field=field,
        old_value=str(old_val), new_value=str(new_val), by=user
    )

def create_account(validated_data, user=None):
    parent = validated_data.get("parent")
    validated_data["level"] = (parent.level + 1) if parent else 0
    validated_data["created_by"] = user

    account = Account.objects.create(**validated_data)
    
    # ✅ Audit Log mein poori details bhejni hai
    detail_str = f"Code: {account.code}, Name: {account.name}, Type: {account.type}, Budget: {account.budget}"
    _log(account, "Created", field="Account Details", old_val="None", new_val=detail_str, user=user)
    
    return account

def update_account(instance, validated_data, user=None):
    if "parent" in validated_data:
        parent = validated_data["parent"]
        validated_data["level"] = (parent.level + 1) if parent else 0

    TRACKED = ["name", "type", "budget", "currency", "status", "linked_module", "note", "parent"]
    
    for field in TRACKED:
        if field not in validated_data:
            continue
        
        old = str(getattr(instance, field) or "—")
        new = str(validated_data[field] or "—")
        
        if old != new:
            # ✅ Field ka naam aur Old/New value dono save hongi
            _log(instance, "Updated", field=field.title(), old_val=old, new_val=new, user=user)

    for attr, val in validated_data.items():
        setattr(instance, attr, val)
    instance.save()
    return instance

def toggle_status(instance, user=None):
    old = instance.status
    instance.status = "inactive" if instance.status == "active" else "active"
    action = "Deactivated" if instance.status == "inactive" else "Activated"
    instance.save(update_fields=["status", "updated_at"])
    
    # ✅ Status change ka log
    _log(instance, action, field="Status", old_val=old, new_val=instance.status, user=user)
    return instance

def delete_account(instance):
    if instance.children.exists():
        raise ValueError(f"Cannot delete '{instance.name}' — it has sub-accounts.")
    instance.delete()
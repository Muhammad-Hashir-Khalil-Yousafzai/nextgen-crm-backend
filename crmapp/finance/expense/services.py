from .models import ExpenseCategory, ExpenseClaim

def create_category(data, user=None):
    parent = data.get('parent')
    data['level'] = (parent.level + 1) if parent else 0
    return ExpenseCategory.objects.create(**data, created_by=user)

def create_claim(data, user=None):
    return ExpenseClaim.objects.create(**data, created_by=user)

def submit_claim(claim):
    if claim.status != "draft": raise ValueError("Only draft claims can be submitted.")
    claim.status = "submitted"; claim.save(update_fields=["status","updated_at"]); return claim

def approve_claim(claim):
    if claim.status != "submitted": raise ValueError("Only submitted claims can be approved.")
    claim.status = "approved"; claim.save(update_fields=["status","updated_at"]); return claim

def pay_claim(claim):
    if claim.status != "approved": raise ValueError("Only approved claims can be paid.")
    claim.status = "paid"; claim.save(update_fields=["status","updated_at"])
    claim.category.spent += claim.amount; claim.category.save(update_fields=["spent"]); return claim

def flag_claim(claim, note=""):
    claim.status = "flagged"
    if note: claim.notes = note
    claim.save(update_fields=["status","notes","updated_at"]); return claim
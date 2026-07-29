from .models import BankAccount, Transaction, Cheque

def create_bank_account(data, user=None):
    return BankAccount.objects.create(**data, created_by=user)

def record_transaction(bank_account, tx_type, amount, date, description, method="", reference="", category=""):
    tx = Transaction.objects.create(bank_account=bank_account, type=tx_type, amount=amount, date=date, description=description, method=method, reference=reference, category=category)
    if tx_type == "receipt":  bank_account.current_balance += amount
    elif tx_type == "payment": bank_account.current_balance -= abs(amount)
    bank_account.save(update_fields=["current_balance"])
    return tx

def update_cheque_status(cheque, new_status):
    cheque.status = new_status
    cheque.save(update_fields=["status"])
    return cheque
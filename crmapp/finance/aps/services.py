import datetime
from decimal import Decimal
from .models import Vendor, Bill, BillItem, APPayment, BillApproval

def create_vendor(data, user=None):
    return Vendor.objects.create(**data, created_by=user)

def create_bill(data, items_data=None, user=None):
    if 'items' in data: data.pop('items')
    items_data = items_data or []
    if items_data:
        calculated_amount = sum(float(item.get('rate') or item.get('price') or 0) * int(item.get('qty') or item.get('quantity') or 1) for item in items_data)
        data['amount'] = Decimal(str(calculated_amount))
        if calculated_amount > 0 and data.get('status', 'draft') == 'draft': data['status'] = 'pending'
    else:
        frontend_amount = data.get('amount') or 0
        data['amount'] = Decimal(str(frontend_amount))
        if float(frontend_amount) > 0 and data.get('status', 'draft') == 'draft': data['status'] = 'pending'

    bill = Bill.objects.create(**data, created_by=user)
    for item in items_data:
        BillItem.objects.create(bill=bill, description=item.get('description') or item.get('desc') or 'Line Item', qty=Decimal(str(item.get('qty') or item.get('quantity') or 1)), rate=Decimal(str(item.get('rate') or item.get('price') or 0)))
    return bill

def approve_bill(bill, role, approver_name, note=""):
    return BillApproval.objects.create(bill=bill, role=role, name=approver_name, status="approved", note=note, date=datetime.date.today())

def record_payment(bill, amount, date, method):
    dec_amount = Decimal(str(amount))
    payment = APPayment.objects.create(bill=bill, amount=dec_amount, date=date, method=method)
    bill.refresh_from_db()
    bill.paid_amount += dec_amount
    bill.status = "paid" if bill.paid_amount >= bill.amount else "partial"
    bill.save(update_fields=["paid_amount", "status", "updated_at"])
    return payment
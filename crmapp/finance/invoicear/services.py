from decimal import Decimal
from .models import Customer, Invoice, InvoiceItem, ARPayment, Dispute

def create_customer(data, user=None):
    return Customer.objects.create(**data, created_by=user)

def update_customer(instance, data):
    for k, v in data.items(): setattr(instance, k, v)
    instance.save()
    return instance

def create_invoice(data, items_data=None, user=None):
    if 'items' in data: data.pop('items')
    items_data = items_data or []
    if items_data:
        calculated_amount = sum(float(item.get('rate') or item.get('price') or 0) * int(item.get('qty') or item.get('quantity') or 1) for item in items_data)
        data['amount'] = Decimal(str(calculated_amount))
    else:
        frontend_amount = data.get('amount') or 0
        data['amount'] = Decimal(str(frontend_amount))

    invoice = Invoice.objects.create(**data, created_by=user)
    for item in items_data:
        InvoiceItem.objects.create(invoice=invoice, description=item.get('description') or item.get('desc') or 'Line Item', qty=Decimal(str(item.get('qty') or item.get('quantity') or 1)), rate=Decimal(str(item.get('rate') or item.get('price') or 0)))
    return invoice

def record_payment(invoice, amount, date, method):
    dec_amount = Decimal(str(amount))
    payment = ARPayment.objects.create(invoice=invoice, amount=dec_amount, date=date, method=method)
    invoice.refresh_from_db()
    invoice.paid_amount += dec_amount
    invoice.status = "paid" if invoice.paid_amount >= invoice.amount else "partially_paid"
    invoice.save(update_fields=["paid_amount", "status", "updated_at"])
    return payment

def raise_dispute(invoice, reason, note=""):
    dispute = Dispute.objects.create(invoice=invoice, reason=reason, note=note)
    invoice.status = "disputed"
    invoice.save(update_fields=["status", "updated_at"])
    return dispute
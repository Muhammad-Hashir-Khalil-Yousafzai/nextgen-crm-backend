from .models import JournalEntry, JournalLine
from django.db import transaction

def create_journal_entry(date, description, reference, source, lines_data):
    total_debit  = sum(l.get('debit',  0) for l in lines_data)
    total_credit = sum(l.get('credit', 0) for l in lines_data)
    if total_debit != total_credit:
        raise ValueError(f"Journal entry not balanced: Dr {total_debit} ≠ Cr {total_credit}")
    entry = JournalEntry.objects.create(date=date, description=description,
                                         reference=reference, source=source, status="draft")
    for line in lines_data:
        JournalLine.objects.create(entry=entry, **line)
    return entry

def post_entry(entry):
    if entry.locked:
        raise ValueError("This entry is locked and cannot be modified.")
    if not entry.is_balanced:
        raise ValueError("Cannot post an unbalanced journal entry.")
    with transaction.atomic():
        entry.status = "posted"
        entry.locked = True
        entry.save(update_fields=["status", "locked", "updated_at"])
        for line in entry.lines.select_related('account'):
            account = line.account
            account.balance += (line.debit - line.credit)
            account.save(update_fields=["balance", "updated_at"])
    return entry

def reverse_entry(entry, reversal_date, description="Reversal"):
    if not entry.locked:
        raise ValueError("Only posted (locked) entries can be reversed.")
    reversal = JournalEntry.objects.create(
        date=reversal_date,
        description=f"REVERSAL: {entry.description}",
        reference=f"REV-{entry.reference}",
        source=entry.source, status="draft"
    )
    for line in entry.lines.all():
        JournalLine.objects.create(entry=reversal, account=line.account,
                                   debit=line.credit, credit=line.debit,
                                   description=f"Reversal of line {line.id}")
    return reversal

def get_account_ledger(account, date_from=None, date_to=None):
    qs = JournalLine.objects.filter(account=account).select_related('entry')
    if date_from: qs = qs.filter(entry__date__gte=date_from)
    if date_to:   qs = qs.filter(entry__date__lte=date_to)
    return qs.order_by('entry__date')
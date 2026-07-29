from django.db import models
from django.conf import settings

class JournalEntry(models.Model):
    SOURCE = [("AR","AR"),("AP","AP"),("Payroll","Payroll"),
              ("Assets","Assets"),("Cash & Bank","Cash & Bank"),("Manual","Manual")]
    STATUS = [("draft","Draft"),("posted","Posted")]

    date        = models.DateField()
    description = models.CharField(max_length=255)
    reference   = models.CharField(max_length=50, blank=True)
    status      = models.CharField(max_length=10, choices=STATUS, default="draft")
    source      = models.CharField(max_length=20, choices=SOURCE, default="Manual")
    locked      = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)
    created_by  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='journal_entries_created')

    class Meta:
        ordering = ['-date','-created_at']

    def __str__(self): return f"JE-{self.id} | {self.reference} | {self.description[:40]}"

    @property
    def total_debit(self):  return sum(l.debit  for l in self.lines.all())
    @property
    def total_credit(self): return sum(l.credit for l in self.lines.all())
    @property
    def is_balanced(self):  return self.total_debit == self.total_credit


class JournalLine(models.Model):
    entry   = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name="lines")
    account = models.ForeignKey(
        "coa.Account", on_delete=models.PROTECT,
        related_name="journal_lines",
        help_text="Must reference a leaf-level COA account"
    )
    debit       = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    credit      = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    description = models.CharField(max_length=255, blank=True)

    def __str__(self): return f"Dr {self.debit} | Cr {self.credit} → {self.account.code}"
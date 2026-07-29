"""
Management Command: train_models
=================================
Run with:  python manage.py train_models

This command reads from your existing CRM tables and trains all 3 AI models.
Run once manually after seeding data, then set a weekly cron job.

Cron (every Monday 2 AM):
  0 2 * * 1  cd /path/to/project && python manage.py train_models >> /var/log/crm_train.log 2>&1
"""

from django.core.management.base import BaseCommand
from django.db.models import Sum
from django.db.models.functions import TruncMonth


class Command(BaseCommand):
    help = "Train all 3 AI models: Lead Scoring, Churn Prediction, Sales Forecast"

    def add_arguments(self, parser):
        parser.add_argument(
            "--model",
            type=str,
            default="all",
            choices=["all", "leads", "churn", "forecast"],
            help="Which model to train (default: all)",
        )

    def handle(self, *args, **options):
        model_choice = options["model"]
        self.stdout.write(self.style.HTTP_INFO("\n══════════════════════════════════════"))
        self.stdout.write(self.style.HTTP_INFO("   BillsMed CRM — AI Model Training"))
        self.stdout.write(self.style.HTTP_INFO("══════════════════════════════════════\n"))

        if model_choice in ("all", "leads"):
            self._train_lead_scoring()

        if model_choice in ("all", "churn"):
            self._train_churn()

        if model_choice in ("all", "forecast"):
            self._train_forecast()

        self.stdout.write(self.style.SUCCESS("\n✓ Training complete!\n"))

    # ── Lead Scoring ──────────────────────────────────────────────────────────
    def _train_lead_scoring(self):
        from crmapp.crm.leads.models import Lead
        from crmapp.analytics.ai import lead_scoring

        self.stdout.write("▶ Training Lead Scoring Model (Random Forest)...")

        qs = Lead.objects.filter(
            status__in=["closed", "lost"]
        ).select_related("company", "contact")

        won_count  = qs.filter(status="closed").count()
        lost_count = qs.filter(status="lost").count()
        self.stdout.write(
            f"  Data: {won_count} won + {lost_count} lost = {won_count + lost_count} total"
        )

        ok, msg = lead_scoring.train(qs)

        if ok:
            self.stdout.write(self.style.SUCCESS(f"  ✓ {msg}"))
            importance = lead_scoring.feature_importance()
            if importance:
                self.stdout.write("  Feature Importance:")
                for fi in importance:
                    bar = "█" * int(fi["importance"] * 40)
                    self.stdout.write(
                        f"    {fi['feature']:<25} {fi['importance']:.4f}  {bar}"
                    )
        else:
            self.stdout.write(self.style.WARNING(f"  ✗ {msg}"))

    # ── Churn Prediction ──────────────────────────────────────────────────────
    def _train_churn(self):
        from crmapp.crm.companies.models import Company
        from crmapp.crm.contacts.models  import Contact
        from crmapp.analytics.ai import churn

        self.stdout.write("\n▶ Training Churn Prediction Model (Logistic Regression)...")

        # Base prefetch — always valid based on your models.py
        prefetch_list = [
            "activities",                  # Activity.company FK → related_name='activities'
            "deals",                       # Deal.company FK     → related_name='deals'
            "contacts",                    # Contact.company FK  → related_name='contacts'
            "contacts__survey_responses",  # SurveyResponse.contact FK
        ]

        # Add ticket/followup prefetch only if related_name exists on Contact
        # Your Contact model has these via FollowUp.contact and Ticket.contact FKs
        try:
            Contact.objects.prefetch_related("tickets").first()
            prefetch_list.append("contacts__tickets")
            self.stdout.write("  ✓ contacts__tickets prefetch available")
        except Exception:
            self.stdout.write("  ℹ contacts__tickets not available (tickets counted via DB query)")

        try:
            Contact.objects.prefetch_related("followups").first()
            prefetch_list.append("contacts__followups")
            self.stdout.write("  ✓ contacts__followups prefetch available")
        except Exception:
            self.stdout.write("  ℹ contacts__followups not available (followups counted via DB query)")

        qs = Company.objects.prefetch_related(*prefetch_list).all()

        self.stdout.write(f"  Data: {qs.count()} companies")
        ok, msg = churn.train(qs)

        if ok:
            self.stdout.write(self.style.SUCCESS(f"  ✓ {msg}"))
        else:
            self.stdout.write(self.style.WARNING(f"  ✗ {msg}"))

    # ── Sales Forecast ────────────────────────────────────────────────────────
    def _train_forecast(self):
        from crmapp.crm.deals.models import Deal
        from crmapp.analytics.ai import forecast

        self.stdout.write("\n▶ Training Sales Forecast Model (Linear Regression)...")

        monthly_qs = (
            Deal.objects.filter(stage="won", close_date__isnull=False)
            .annotate(month=TruncMonth("close_date"))
            .values("month")
            .annotate(revenue=Sum("value"))
            .order_by("month")
        )

        monthly_list = [float(row["revenue"] or 0) for row in monthly_qs]
        self.stdout.write(f"  Data: {len(monthly_list)} months of revenue history")

        if monthly_list:
            total = sum(monthly_list)
            avg   = total / len(monthly_list)
            self.stdout.write(f"  Total revenue in data: ${total:,.0f}")
            self.stdout.write(f"  Average monthly revenue: ${avg:,.0f}")

        ok, msg = forecast.train(monthly_list)
        if ok:
            self.stdout.write(self.style.SUCCESS(f"  ✓ {msg}"))
            predictions = forecast.predict(n_months=3, history_length=len(monthly_list))
            self.stdout.write("  Next 3-Month Forecast:")
            for p in predictions:
                self.stdout.write(
                    f"    {p['month']:<12} "
                    f"Forecast: ${p['forecast']:>10,.0f}  |  "
                    f"Low: ${p['low']:>10,.0f}  |  "
                    f"High: ${p['high']:>10,.0f}"
                )
        else:
            self.stdout.write(self.style.WARNING(f"  ✗ {msg}"))
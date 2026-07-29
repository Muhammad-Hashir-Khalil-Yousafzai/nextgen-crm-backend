"""
crmapp/xai/management/commands/train_xai_models.py

Trains and saves all XAI models.

Usage:
  python manage.py train_xai_models               # synthetic data (Phase 1)
  python manage.py train_xai_models --real         # real CRM data (Phase 2)
  python manage.py train_xai_models --model leads  # only lead model
"""

from django.core.management.base import BaseCommand
from crmapp.ai.xai.services import train_lead_conversion_model, train_deal_win_model
from crmapp.ai.xai.models import MLModel


class Command(BaseCommand):
    help = "Trains XAI models from CRM data (synthetic or real)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--real",
            action  = "store_true",
            default = False,
            help    = "Use real CRM data instead of synthetic (needs enough records).",
        )
        parser.add_argument(
            "--model",
            type    = str,
            default = "all",
            choices = ["all", "leads", "deals"],
            help    = "Which model to train.",
        )

    def handle(self, *args, **options):
        use_real = options["real"]
        which    = options["model"]

        data_source = "real CRM data" if use_real else "synthetic data"
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\nTraining XAI models using {data_source}...\n"
        ))

        # Ensure MLModel records exist
        MLModel.objects.get_or_create(
            name         = "Lead Conversion Predictor",
            defaults     = {
                "model_type":  "Random Forest",
                "domain":      "Marketing",
                "description": "Predicts likelihood of a lead converting to a deal.",
                "active":      True,
            },
        )
        MLModel.objects.get_or_create(
            name         = "Deal Win Predictor",
            defaults     = {
                "model_type":  "XGBoost",
                "domain":      "Finance",
                "description": "Predicts likelihood of a deal being won.",
                "active":      True,
            },
        )

        results = {}

        if which in ("all", "leads"):
            self.stdout.write("  Training Lead Conversion Predictor (Random Forest)...")
            try:
                r = train_lead_conversion_model(use_real_data=use_real)
                results["leads"] = r
                self.stdout.write(self.style.SUCCESS(
                    f"  ✓ Lead model — accuracy: {r['accuracy']}% | F1: {r['f1']}% | "
                    f"rows: {r['rows']} | saved: {r['file_path']}"
                ))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ Lead model failed: {e}"))

        if which in ("all", "deals"):
            self.stdout.write("  Training Deal Win Predictor (XGBoost)...")
            try:
                r = train_deal_win_model(use_real_data=use_real)
                results["deals"] = r
                self.stdout.write(self.style.SUCCESS(
                    f"  ✓ Deal model — accuracy: {r['accuracy']}% | F1: {r['f1']}% | "
                    f"rows: {r['rows']} | saved: {r['file_path']}"
                ))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ Deal model failed: {e}"))

        self.stdout.write(self.style.SUCCESS("\nDone. Models are live.\n"))
        self.stdout.write(
            "Next: POST to /api/xai/predictions/{id}/explain/ to generate explanations.\n"
        )

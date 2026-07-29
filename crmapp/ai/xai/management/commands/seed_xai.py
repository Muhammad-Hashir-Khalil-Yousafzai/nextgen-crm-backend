"""
crmapp/xai/management/commands/seed_xai.py

Seeds the XAI module with demo data matching the React frontend.
Run with:  python manage.py seed_xai
"""

from django.core.management.base import BaseCommand
from crmapp.ai.xai.models import (
    MLModel, Prediction, Explanation,
    FeatureContribution, Counterfactual,
    BiasAudit, BiasAuditGroup, ModelIssue, GlobalImportance,
)


MODELS_DATA = [
    {
        "name":        "Loan Risk Classifier",
        "model_type":  "Gradient Boosting",
        "domain":      "Finance",
        "description": "Predicts loan approval/rejection risk based on applicant financial profile.",
        "accuracy":    91.40,
    },
    {
        "name":        "Churn Predictor v3",
        "model_type":  "Random Forest",
        "domain":      "Marketing",
        "description": "Predicts customer churn probability based on engagement and support signals.",
        "accuracy":    87.20,
    },
    {
        "name":        "Disease Risk Model",
        "model_type":  "Neural Network",
        "domain":      "Healthcare",
        "description": "Predicts cardiovascular disease risk based on clinical measurements.",
        "accuracy":    89.60,
    },
    {
        "name":        "HR Screening AI",
        "model_type":  "XGBoost",
        "domain":      "HR",
        "description": "Screens and shortlists job applicants based on skills and experience match.",
        "accuracy":    93.10,
    },
]

PREDICTIONS_DATA = [
    {
        "model_name":       "Loan Risk Classifier",
        "subject_id":       "USR-8812",
        "subject_name":     "Ahmed Al-Rashidi",
        "subject_type":     "customer",
        "prediction_label": "Rejected",
        "outcome_type":     "negative",
        "confidence_score": 0.87,
        "uncertainty_score":0.13,
        "raw_input": {
            "Debt-to-Income Ratio": 0.52,
            "Credit History":       1,
            "Loan Amount":          48000,
            "Employment Duration":  8,
            "Annual Income":        62000,
            "Collateral Value":     28000,
        },
        "explainer":        "SHAP",
        "initiated_by":     "Risk Engine",
        "nl_explanation":   (
            "This application was rejected primarily because the debt-to-income ratio "
            "exceeds acceptable thresholds and the credit history shows two late payments "
            "in the past 12 months. The requested loan amount is also high relative to "
            "verified annual income."
        ),
        "features": [
            {"name": "Debt-to-Income Ratio", "value": "0.52",    "shap": -0.38, "importance": 0.38},
            {"name": "Credit History",       "value": "Poor",    "shap": -0.29, "importance": 0.29},
            {"name": "Loan Amount",          "value": "$48,000", "shap": -0.14, "importance": 0.14},
            {"name": "Employment Duration",  "value": "8 mo",    "shap": -0.09, "importance": 0.09},
            {"name": "Annual Income",        "value": "$62,000", "shap": +0.12, "importance": 0.12},
            {"name": "Collateral Value",     "value": "$28,000", "shap": +0.07, "importance": 0.07},
        ],
        "counterfactuals": [
            {"idx": 1, "change": "Reduce debt-to-income ratio to < 0.35",  "impact": "Rejection → Approved",    "prob": 0.74},
            {"idx": 2, "change": "Improve credit score by 80 points",       "impact": "Rejection → Approved",    "prob": 0.68},
            {"idx": 3, "change": "Reduce loan amount to < $32,000",         "impact": "Rejection → Borderline",  "prob": 0.51},
        ],
    },
    {
        "model_name":       "Churn Predictor v3",
        "subject_id":       "USR-7741",
        "subject_name":     "Fatima Malik",
        "subject_type":     "customer",
        "prediction_label": "High Churn Risk",
        "outcome_type":     "negative",
        "confidence_score": 0.82,
        "uncertainty_score":0.18,
        "raw_input": {
            "Days Since Last Login": 47,
            "Support Ticket Age":    9,
            "Subscription Tier":     0,
            "Usage Frequency":       1,
            "Contract Months Left":  2,
            "NPS Score":             6,
        },
        "explainer":        "LIME",
        "initiated_by":     "CRM Bot",
        "nl_explanation":   (
            "This customer has a high churn probability because they have not logged in "
            "for 47 days, their last support ticket was unresolved for 9 days, and their "
            "subscription tier was recently downgraded."
        ),
        "features": [
            {"name": "Days Since Last Login",  "value": "47 days","shap": -0.41, "importance": 0.41},
            {"name": "Support Ticket Age",     "value": "9 days", "shap": -0.27, "importance": 0.27},
            {"name": "Subscription Tier",      "value": "Basic",  "shap": -0.18, "importance": 0.18},
            {"name": "Usage Frequency",        "value": "Low",    "shap": -0.12, "importance": 0.12},
            {"name": "Contract Months Left",   "value": "2 mo",   "shap": +0.08, "importance": 0.08},
            {"name": "NPS Score",              "value": "6",      "shap": +0.04, "importance": 0.04},
        ],
        "counterfactuals": [
            {"idx": 1, "change": "Resolve open support ticket immediately",     "impact": "High Risk → Medium Risk", "prob": 0.61},
            {"idx": 2, "change": "Customer logs in within next 7 days",         "impact": "High Risk → Medium Risk", "prob": 0.55},
            {"idx": 3, "change": "Offer upgrade to Pro tier with 20% discount", "impact": "High Risk → Low Risk",    "prob": 0.48},
        ],
    },
    {
        "model_name":       "Disease Risk Model",
        "subject_id":       "PAT-0391",
        "subject_name":     "Patient #A-0391",
        "subject_type":     "patient",
        "prediction_label": "Elevated CVD Risk",
        "outcome_type":     "warning",
        "confidence_score": 0.79,
        "uncertainty_score":0.21,
        "raw_input": {
            "Systolic Blood Pressure": 148,
            "LDL Cholesterol":         162,
            "Family History":          1,
            "Physical Activity":       0,
            "BMI":                     28.4,
            "Non-Smoker Status":       1,
            "Age":                     54,
        },
        "explainer":        "SHAP",
        "initiated_by":     "Dr. AI Agent",
        "nl_explanation":   (
            "The patient shows elevated cardiovascular disease risk based on a combination "
            "of high systolic blood pressure, elevated LDL cholesterol, and a family history "
            "of heart disease. Lifestyle factors such as low physical activity further increase risk."
        ),
        "features": [
            {"name": "Systolic Blood Pressure","value": "148 mmHg","shap": -0.33, "importance": 0.33},
            {"name": "LDL Cholesterol",        "value": "162 mg/dL","shap": -0.28, "importance": 0.28},
            {"name": "Family History",         "value": "Positive", "shap": -0.21, "importance": 0.21},
            {"name": "Physical Activity",      "value": "Sedentary","shap": -0.11, "importance": 0.11},
            {"name": "BMI",                    "value": "28.4",     "shap": -0.08, "importance": 0.08},
            {"name": "Non-Smoker Status",      "value": "Yes",      "shap": +0.14, "importance": 0.14},
            {"name": "Age",                    "value": "54",       "shap": -0.09, "importance": 0.09},
        ],
        "counterfactuals": [
            {"idx": 1, "change": "Reduce systolic BP to < 130 mmHg",    "impact": "Elevated → Moderate Risk", "prob": 0.66},
            {"idx": 2, "change": "Lower LDL to < 130 mg/dL",            "impact": "Elevated → Moderate Risk", "prob": 0.58},
            {"idx": 3, "change": "Begin moderate exercise 3x per week", "impact": "Elevated → Moderate Risk", "prob": 0.44},
        ],
    },
    {
        "model_name":       "HR Screening AI",
        "subject_id":       "APP-2291",
        "subject_name":     "Zainab Noor",
        "subject_type":     "applicant",
        "prediction_label": "Shortlisted",
        "outcome_type":     "positive",
        "confidence_score": 0.91,
        "uncertainty_score":0.09,
        "raw_input": {
            "Years of Experience": 7,
            "Skills Match Score":  91,
            "Domain Background":   1,
            "Communication Score": 88,
            "Education Level":     2,
            "Gap in Employment":   8,
        },
        "explainer":        "TreeSHAP",
        "initiated_by":     "HR Bot",
        "nl_explanation":   (
            "This candidate has been shortlisted due to strong alignment with role requirements. "
            "The applicant has 7 years of relevant experience, a high skills-match score of 91%, "
            "and previous employment at companies with domain expertise."
        ),
        "features": [
            {"name": "Years of Experience",  "value": "7 yrs",   "shap": +0.36, "importance": 0.36},
            {"name": "Skills Match Score",   "value": "91%",     "shap": +0.28, "importance": 0.28},
            {"name": "Domain Background",    "value": "Strong",  "shap": +0.19, "importance": 0.19},
            {"name": "Communication Score",  "value": "Top 12%", "shap": +0.12, "importance": 0.12},
            {"name": "Education Level",      "value": "BSc",     "shap": +0.05, "importance": 0.05},
            {"name": "Gap in Employment",    "value": "8 mo",    "shap": -0.07, "importance": 0.07},
        ],
        "counterfactuals": [],
    },
]


class Command(BaseCommand):
    help = "Seeds the XAI module with demo data matching the React frontend."

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.MIGRATE_HEADING("Seeding XAI module..."))

        # ── 1. Models ─────────────────────────────────────────────────────────
        model_map = {}
        for m in MODELS_DATA:
            obj, created = MLModel.objects.get_or_create(
                name=m["name"],
                defaults={k: v for k, v in m.items() if k != "name"},
            )
            model_map[obj.name] = obj
            status = "created" if created else "exists"
            self.stdout.write(f"  MLModel [{status}]: {obj.name}")

        # ── 2. Predictions + Explanations + Features + Counterfactuals ────────
        for p in PREDICTIONS_DATA:
            ml_model = model_map[p["model_name"]]

            pred, created = Prediction.objects.get_or_create(
                subject_id   = p["subject_id"],
                model        = ml_model,
                defaults={
                    "subject_name":     p["subject_name"],
                    "subject_type":     p["subject_type"],
                    "prediction_label": p["prediction_label"],
                    "outcome_type":     p["outcome_type"],
                    "confidence_score": p["confidence_score"],
                    "uncertainty_score":p["uncertainty_score"],
                    "raw_input":        p["raw_input"],
                },
            )
            self.stdout.write(f"  Prediction [{'created' if created else 'exists'}]: {pred.id} — {pred.subject_name}")

            if created:
                expl = Explanation.objects.create(
                    prediction     = pred,
                    explainer_used = p["explainer"],
                    nl_explanation = p["nl_explanation"],
                    initiated_by   = p["initiated_by"],
                    shap_values    = {f["name"]: f["shap"] for f in p["features"]},
                )

                max_imp = max(f["importance"] for f in p["features"])
                for rank, f in enumerate(
                    sorted(p["features"], key=lambda x: x["importance"], reverse=True),
                    start=1,
                ):
                    FeatureContribution.objects.create(
                        explanation       = expl,
                        feature_name      = f["name"],
                        feature_value     = f["value"],
                        shap_contribution = f["shap"],
                        direction         = "positive" if f["shap"] >= 0 else "negative",
                        importance_score  = round(f["importance"] / max_imp, 4),
                        rank              = rank,
                    )

                for cf in p["counterfactuals"]:
                    Counterfactual.objects.create(
                        prediction         = pred,
                        scenario_index     = cf["idx"],
                        change_description = cf["change"],
                        impact_label       = cf["impact"],
                        probability        = cf["prob"],
                    )

        # ── 3. Bias Audits ────────────────────────────────────────────────────
        loan_model = model_map["Loan Risk Classifier"]
        hr_model   = model_map["HR Screening AI"]
        churn_model= model_map["Churn Predictor v3"]

        for audit_def in [
            {
                "model": loan_model, "attr": "Gender", "disparity": 0.09, "severity": "medium",
                "mitigation": "Apply equalized odds post-processing. Retrain with balanced gender distribution.",
                "groups": [
                    {"label": "Male",   "rate": 0.64, "size": 4821, "flagged": False},
                    {"label": "Female", "rate": 0.58, "size": 3944, "flagged": True},
                ],
            },
            {
                "model": loan_model, "attr": "Age Group", "disparity": 0.14, "severity": "high",
                "mitigation": "Audit age-correlated proxy features. Remove employment-duration bias for younger applicants.",
                "groups": [
                    {"label": "18-35", "rate": 0.54, "size": 2211, "flagged": True},
                    {"label": "36-55", "rate": 0.68, "size": 3982, "flagged": False},
                    {"label": "55+",   "rate": 0.61, "size": 1888, "flagged": False},
                ],
            },
            {
                "model": hr_model, "attr": "Gender", "disparity": 0.03, "severity": "low",
                "mitigation": "No immediate action required. Continue monitoring quarterly.",
                "groups": [
                    {"label": "Male",   "rate": 0.47, "size": 1820, "flagged": False},
                    {"label": "Female", "rate": 0.44, "size": 1644, "flagged": False},
                ],
            },
            {
                "model": churn_model, "attr": "Region", "disparity": 0.08, "severity": "medium",
                "mitigation": "Add rural-specific features. Review if connectivity patterns are proxies for churn.",
                "groups": [
                    {"label": "Urban", "rate": 0.71, "size": 5521, "flagged": False},
                    {"label": "Rural", "rate": 0.63, "size": 2104, "flagged": True},
                ],
            },
        ]:
            if not BiasAudit.objects.filter(model=audit_def["model"], protected_attribute=audit_def["attr"]).exists():
                audit = BiasAudit.objects.create(
                    model               = audit_def["model"],
                    protected_attribute = audit_def["attr"],
                    disparity_score     = audit_def["disparity"],
                    severity            = audit_def["severity"],
                    mitigation_text     = audit_def["mitigation"],
                )
                for g in audit_def["groups"]:
                    BiasAuditGroup.objects.create(
                        audit       = audit,
                        group_label = g["label"],
                        rate_value  = g["rate"],
                        sample_size = g["size"],
                        is_flagged  = g["flagged"],
                    )
                self.stdout.write(f"  BiasAudit [created]: {audit_def['model'].name} — {audit_def['attr']}")

        # ── 4. Model Issues ───────────────────────────────────────────────────
        for issue_def in [
            {
                "model": loan_model,
                "type": "Feature Leakage", "severity": "high",
                "desc": "'Employment ID' is highly correlated with 'Loan Outcome' in training data — likely a data leakage proxy.",
                "rec":  "Remove 'Employment ID' from feature set. Retrain and validate on holdout set.",
                "drift": 0.21, "affected": 142,
            },
            {
                "model": churn_model,
                "type": "Distribution Shift", "severity": "medium",
                "desc": "'Days Since Last Login' distribution has shifted significantly vs training data.",
                "rec":  "Retrain on recent 6-month data. Add drift monitoring alert at 10% threshold.",
                "drift": 0.14, "affected": 88,
            },
            {
                "model": hr_model,
                "type": "Low Confidence Region", "severity": "low",
                "desc": "Predictions for applicants with employment gaps > 12 months have confidence below 70%.",
                "rec":  "Gather more labeled examples for candidates with long employment gaps.",
                "drift": 0.08, "affected": 31,
            },
        ]:
            if not ModelIssue.objects.filter(model=issue_def["model"], issue_type=issue_def["type"]).exists():
                ModelIssue.objects.create(
                    model          = issue_def["model"],
                    issue_type     = issue_def["type"],
                    severity       = issue_def["severity"],
                    description    = issue_def["desc"],
                    recommendation = issue_def["rec"],
                    shap_drift     = issue_def["drift"],
                    affected_count = issue_def["affected"],
                )
                self.stdout.write(f"  ModelIssue [created]: {issue_def['type']} on {issue_def['model'].name}")

        self.stdout.write(self.style.SUCCESS("\nXAI seed complete."))

"""
crmapp/xai/models.py

All XAI database tables.
ID format mirrors your project: short prefixed strings (e.g. mdl-abc123)
"""

import uuid
from django.db import models


# ── ID generators ─────────────────────────────────────────────────────────────

def make_model_id():
    return f"mdl-{uuid.uuid4().hex[:6]}"

def make_pred_id():
    return f"pred-{uuid.uuid4().hex[:6]}"

def make_expl_id():
    return f"expl-{uuid.uuid4().hex[:6]}"

def make_feat_id():
    return f"feat-{uuid.uuid4().hex[:6]}"

def make_cf_id():
    return f"cf-{uuid.uuid4().hex[:6]}"

def make_bias_id():
    return f"bias-{uuid.uuid4().hex[:6]}"

def make_issue_id():
    return f"iss-{uuid.uuid4().hex[:6]}"

def make_gimp_id():
    return f"gimp-{uuid.uuid4().hex[:6]}"


# ── 1. MLModel ────────────────────────────────────────────────────────────────

class MLModel(models.Model):
    """
    Registry of every ML model the XAI layer supports.
    One row per model (e.g. Loan Risk Classifier, Churn Predictor v3).
    """
    DOMAIN_CHOICES = [
        ("Finance",    "Finance"),
        ("Marketing",  "Marketing"),
        ("Healthcare", "Healthcare"),
        ("HR",         "HR"),
        ("General",    "General"),
    ]

    id           = models.CharField(max_length=50, primary_key=True, default=make_model_id)
    name         = models.CharField(max_length=200, unique=True)
    model_type   = models.CharField(max_length=100)          # XGBoost, Random Forest, etc.
    domain       = models.CharField(max_length=50, choices=DOMAIN_CHOICES, default="General")
    description  = models.TextField(blank=True, default="")
    file_path    = models.CharField(max_length=500, blank=True, default="")  # path to .pkl
    accuracy     = models.FloatField(null=True, blank=True)  # e.g. 91.40
    active       = models.BooleanField(default=True)
    extra        = models.JSONField(default=dict, blank=True) # any extra metadata
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "xai_models"
        ordering = ["domain", "name"]

    def __str__(self):
        return f"{self.name} ({self.domain})"

    @property
    def total_predictions(self):
        return self.predictions.count()

    @property
    def open_issues(self):
        return self.issues.filter(resolved=False).count()


# ── 2. Prediction ─────────────────────────────────────────────────────────────

class Prediction(models.Model):
    """
    One row per prediction your models make.
    Linked to the model that made it.
    """
    OUTCOME_CHOICES = [
        ("positive", "Positive"),
        ("negative", "Negative"),
        ("warning",  "Warning"),
    ]

    id               = models.CharField(max_length=50, primary_key=True, default=make_pred_id)
    model            = models.ForeignKey(
        MLModel,
        on_delete=models.CASCADE,
        related_name="predictions",
    )
    subject_id       = models.CharField(max_length=100)      # e.g. "USR-8812"
    subject_type     = models.CharField(max_length=100)      # customer | patient | applicant
    subject_name     = models.CharField(max_length=200, blank=True, default="")
    prediction_label = models.CharField(max_length=200)      # e.g. "Rejected"
    outcome_type     = models.CharField(max_length=20, choices=OUTCOME_CHOICES)
    confidence_score = models.FloatField()                   # 0.0 – 1.0
    uncertainty_score= models.FloatField(null=True, blank=True)
    raw_input        = models.JSONField(default=dict, blank=True)  # original feature dict
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "xai_predictions"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.model.name} → {self.subject_id}: {self.prediction_label}"


# ── 3. Explanation ────────────────────────────────────────────────────────────

class Explanation(models.Model):
    """
    The XAI output for a single prediction.
    Contains the NL explanation and raw SHAP values.
    """
    EXPLAINER_CHOICES = [
        ("SHAP",           "SHAP"),
        ("LIME",           "LIME"),
        ("TreeSHAP",       "TreeSHAP"),
        ("Integrated G",   "Integrated Gradients"),
    ]

    id             = models.CharField(max_length=50, primary_key=True, default=make_expl_id)
    prediction     = models.OneToOneField(
        Prediction,
        on_delete=models.CASCADE,
        related_name="explanation",
    )
    explainer_used = models.CharField(max_length=50, choices=EXPLAINER_CHOICES, default="SHAP")
    nl_explanation = models.TextField(blank=True, default="")   # human-readable text
    shap_values    = models.JSONField(default=dict, blank=True)  # raw SHAP output
    base_value     = models.FloatField(null=True, blank=True)    # SHAP base/expected value
    initiated_by   = models.CharField(max_length=200, blank=True, default="")  # e.g. "Risk Engine"
    exported       = models.BooleanField(default=False)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "xai_explanations"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Explanation for {self.prediction_id} via {self.explainer_used}"


# ── 4. FeatureContribution ────────────────────────────────────────────────────

class FeatureContribution(models.Model):
    """
    Per-feature SHAP breakdown.
    One row per feature per explanation.
    """
    DIRECTION_CHOICES = [
        ("positive", "Positive"),
        ("negative", "Negative"),
    ]

    id                = models.CharField(max_length=50, primary_key=True, default=make_feat_id)
    explanation       = models.ForeignKey(
        Explanation,
        on_delete=models.CASCADE,
        related_name="feature_contributions",
    )
    feature_name      = models.CharField(max_length=200)   # "Debt-to-Income Ratio"
    feature_value     = models.CharField(max_length=200, blank=True, default="")  # "0.52"
    shap_contribution = models.FloatField()                # can be negative: -0.38
    direction         = models.CharField(max_length=20, choices=DIRECTION_CHOICES)
    importance_score  = models.FloatField(null=True, blank=True)  # absolute importance 0–1
    rank              = models.IntegerField(null=True, blank=True) # 1 = most important

    class Meta:
        db_table = "xai_feature_contributions"
        ordering = ["-importance_score"]

    def __str__(self):
        return f"{self.feature_name}: {self.shap_contribution:+.3f}"


# ── 5. Counterfactual ─────────────────────────────────────────────────────────

class Counterfactual(models.Model):
    """
    "What-if" scenarios: minimal changes that would flip the prediction.
    Generated by DiCE engine.
    """
    id                  = models.CharField(max_length=50, primary_key=True, default=make_cf_id)
    prediction          = models.ForeignKey(
        Prediction,
        on_delete=models.CASCADE,
        related_name="counterfactuals",
    )
    scenario_index      = models.IntegerField()             # 1, 2, 3
    change_description  = models.TextField()               # "Reduce DTI to < 0.35"
    impact_label        = models.CharField(max_length=200) # "Rejection → Approved"
    probability         = models.FloatField()              # 0.74
    created_at          = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "xai_counterfactuals"
        ordering = ["scenario_index"]

    def __str__(self):
        return f"CF {self.scenario_index} for {self.prediction_id}: {self.impact_label}"


# ── 6. BiasAudit ──────────────────────────────────────────────────────────────

class BiasAudit(models.Model):
    """
    Fairness check for a model against a protected attribute.
    Run periodically (daily / weekly) as a background job.
    """
    SEVERITY_CHOICES = [
        ("low",    "Low"),
        ("medium", "Medium"),
        ("high",   "High"),
    ]

    id                  = models.CharField(max_length=50, primary_key=True, default=make_bias_id)
    model               = models.ForeignKey(
        MLModel,
        on_delete=models.CASCADE,
        related_name="bias_audits",
    )
    protected_attribute = models.CharField(max_length=100)  # "Gender" | "Age Group"
    disparity_score     = models.FloatField()               # e.g. 0.09
    severity            = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    mitigation_text     = models.TextField(blank=True, default="")
    run_at              = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "xai_bias_audits"
        ordering = ["-run_at"]

    def __str__(self):
        return f"{self.model.name} — {self.protected_attribute} ({self.severity})"


# ── 7. BiasAuditGroup ─────────────────────────────────────────────────────────

class BiasAuditGroup(models.Model):
    """
    Per-group breakdown inside a BiasAudit.
    E.g. Male vs Female rows inside a Gender audit.
    """
    id          = models.CharField(max_length=50, primary_key=True, default=make_bias_id)
    audit       = models.ForeignKey(
        BiasAudit,
        on_delete=models.CASCADE,
        related_name="groups",
    )
    group_label = models.CharField(max_length=100)   # "Male", "Female", "18-35"
    rate_value  = models.FloatField()                # approval / shortlist / retention rate
    sample_size = models.IntegerField()
    is_flagged  = models.BooleanField(default=False)

    class Meta:
        db_table = "xai_bias_audit_groups"

    def __str__(self):
        return f"{self.audit} — {self.group_label}: {self.rate_value:.0%}"


# ── 8. ModelIssue ─────────────────────────────────────────────────────────────

class ModelIssue(models.Model):
    """
    Debugging flags: feature leakage, distribution shift, low confidence zones.
    Detected automatically by background monitoring jobs.
    """
    SEVERITY_CHOICES = [
        ("low",    "Low"),
        ("medium", "Medium"),
        ("high",   "High"),
    ]

    id             = models.CharField(max_length=50, primary_key=True, default=make_issue_id)
    model          = models.ForeignKey(
        MLModel,
        on_delete=models.CASCADE,
        related_name="issues",
    )
    issue_type     = models.CharField(max_length=100)  # "Feature Leakage" | "Distribution Shift"
    severity       = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    description    = models.TextField()
    recommendation = models.TextField(blank=True, default="")
    shap_drift     = models.FloatField(null=True, blank=True)   # drift magnitude
    affected_count = models.IntegerField(default=0)
    resolved       = models.BooleanField(default=False)
    detected_at    = models.DateTimeField(auto_now_add=True)
    resolved_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "xai_model_issues"
        ordering = ["-detected_at"]

    def __str__(self):
        return f"{self.model.name} — {self.issue_type} [{self.severity}]"


# ── 9. GlobalImportance ───────────────────────────────────────────────────────

class GlobalImportance(models.Model):
    """
    Aggregated feature importance across ALL predictions for a model.
    Recomputed by a background job (e.g. nightly Celery beat task).
    """
    id             = models.CharField(max_length=50, primary_key=True, default=make_gimp_id)
    model          = models.ForeignKey(
        MLModel,
        on_delete=models.CASCADE,
        related_name="global_importances",
    )
    feature_name   = models.CharField(max_length=200)
    avg_importance = models.FloatField()   # mean |SHAP| across all predictions
    sample_count   = models.IntegerField() # how many predictions this is based on
    computed_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "xai_global_importance"
        ordering = ["-avg_importance"]

    def __str__(self):
        return f"{self.model.name} — {self.feature_name}: {self.avg_importance:.3f}"

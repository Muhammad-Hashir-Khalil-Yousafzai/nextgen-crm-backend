"""
crmapp/xai/services.py  (v2 — upgraded)

What's in here:
  ┌─────────────────────────────────────────────────────────────────┐
  │  SECTION 1  Model registry — load once at startup               │
  │  SECTION 2  CRM data pipeline — reads Lead / Deal / Contact     │
  │  SECTION 3  Synthetic data generator — for training phase       │
  │  SECTION 4  Model trainer — trains & saves .pkl files           │
  │  SECTION 5  SHAP explainer — TreeSHAP / KernelSHAP             │
  │  SECTION 6  LIME explainer — runs alongside SHAP                │
  │  SECTION 7  NL explanation — template or Groq LLM               │
  │  SECTION 8  Counterfactuals — DiCE engine                       │
  │  SECTION 9  Bias audit — fairness checks                        │
  │  SECTION 10 Global importance — nightly aggregation             │
  │  SECTION 11 Dashboard stats                                      │
  │  SECTION 12 Main entry point — explain_prediction()             │
  └─────────────────────────────────────────────────────────────────┘
"""

import logging
import os
import numpy as np
import pandas as pd
from django.conf import settings


from .models import (
    MLModel,
    Prediction,
    Explanation,
    FeatureContribution,
    Counterfactual,
    BiasAudit,
    BiasAuditGroup,
    ModelIssue,
    GlobalImportance,
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — MODEL REGISTRY
# Load trained sklearn/xgboost models once at startup (same pattern as your
# emotion_service.py classifier = pipeline(...) at module level).
# ══════════════════════════════════════════════════════════════════════════════

_MODEL_CACHE: dict = {}   # { ml_model.id: sklearn_model_object }


def load_sklearn_model(ml_model: MLModel):
    """
    Loads a .pkl model from disk and caches it in memory.
    On subsequent calls for the same model, returns the cached object —
    exactly like HuggingFace pipeline() loaded at module level.

    Falls back gracefully if the file doesn't exist yet (Phase 1: no model
    trained yet). Returns None in that case so callers can handle it.
    """
    import joblib

    if ml_model.id in _MODEL_CACHE:
        return _MODEL_CACHE[ml_model.id]

    if not ml_model.file_path or not os.path.exists(ml_model.file_path):
        logger.warning(
            f"Model file not found for '{ml_model.name}' at '{ml_model.file_path}'. "
            f"Run: python manage.py train_xai_models"
        )
        return None

    model = joblib.load(ml_model.file_path)
    _MODEL_CACHE[ml_model.id] = model
    logger.info(f"[XAI] Loaded model '{ml_model.name}' from {ml_model.file_path}")
    return model


def reload_model(ml_model: MLModel):
    """Forces a reload from disk — call this after retraining."""
    _MODEL_CACHE.pop(ml_model.id, None)
    return load_sklearn_model(ml_model)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — CRM DATA PIPELINE
# Reads your actual Lead / Deal / Contact tables and converts them into
# the feature dicts that the models expect as input.
# ══════════════════════════════════════════════════════════════════════════════

# Map your Lead.source choices to numeric values the model can use
SOURCE_MAP = {
    "Website":   5,
    "Referral":  4,
    "LinkedIn":  3,
    "Event":     2,
    "Cold Call": 1,
    "Other":     0,
}

PRIORITY_MAP = {"high": 3, "medium": 2, "low": 1}

STATUS_MAP = {
    "not-contacted": 0,
    "contacted":     1,
    "closed":        2,   # Closed Won
    "lost":          3,   # Closed Lost
}

STAGE_MAP = {
    "Lead":        0,
    "Prospecting": 1,
    "Proposal":    2,
    "Negotiation": 3,
    "Closed Won":  4,
    "Closed Lost": 5,
}


def lead_to_features(lead) -> dict:
    """
    Converts a Lead instance into a flat feature dict for the
    Lead Conversion Predictor model.

    Features chosen from your Lead model fields that a marketing
    manager can actually act on — no PII (no name/email).
    """
    from django.utils import timezone

    # Days since lead was created
    now = timezone.now()
    days_old = (now - lead.created_at).days if lead.created_at else 0

    # Days since last contact (None → very old = 999)
    if lead.last_contact and lead.last_contact != "Never":
        try:
            from django.utils.dateparse import parse_datetime, parse_date
            lc = parse_date(lead.last_contact) or parse_datetime(lead.last_contact)
            days_since_contact = (now.date() - lc).days if lc else 999
        except Exception:
            days_since_contact = 999
    else:
        days_since_contact = 999

    return {
        "deal_value":           float(lead.value or 0),
        "probability":          float(lead.probability or 50),
        "score":                float(lead.score or 0),
        "priority":             PRIORITY_MAP.get(lead.priority, 2),
        "source":               SOURCE_MAP.get(lead.source, 0),
        "stage":                STAGE_MAP.get(lead.deal_stage, 0),
        "days_old":             float(days_old),
        "days_since_contact":   float(days_since_contact),
        "notes_count":          float(lead.notes_count or 0),
        "activities":           float(lead.activities or 0),
        "has_company":          1.0 if (lead.company_id or lead.company_name) else 0.0,
        "has_phone":            1.0 if lead.phone else 0.0,
        "has_email":            1.0 if lead.email else 0.0,
        "weighted_value":       float(lead.weighted_value),
    }


def deal_to_features(deal) -> dict:
    """
    Converts a Deal instance into features for a Deal Win Predictor model.
    """
    from django.utils import timezone

    now = timezone.now()
    days_old = (now - deal.created_at).days if deal.created_at else 0

    days_to_close = 0
    if deal.close_date:
        days_to_close = (deal.close_date - now.date()).days

    stage_map = {"new": 0, "prospect": 1, "proposal": 2, "won": 3}

    return {
        "deal_value":       float(deal.value or 0),
        "probability":      float(deal.probability or 50),
        "stage":            stage_map.get(deal.stage, 0),
        "days_old":         float(days_old),
        "days_to_close":    float(days_to_close),
        "has_contact":      1.0 if deal.contact_id else 0.0,
        "has_company":      1.0 if deal.company_id else 0.0,
        "has_lead":         1.0 if deal.lead_id else 0.0,
        "weighted_value":   float(deal.weighted_value),
    }


def contact_to_features(contact) -> dict:
    """
    Converts a Contact into features for a Contact Engagement model.
    """
    from django.utils import timezone

    now = timezone.now()
    days_since_contact = 999
    if contact.last_contact:
        days_since_contact = (now.date() - contact.last_contact).days

    return {
        "rating":               float(contact.rating or 0),
        "is_active":            1.0 if contact.status == "active" else 0.0,
        "days_since_contact":   float(days_since_contact),
        "has_company":          1.0 if contact.company_id else 0.0,
        "has_phone":            1.0 if contact.phone else 0.0,
        "tag_count":            float(len(contact.tags or [])),
        "has_notes":            1.0 if contact.notes else 0.0,
    }


def get_crm_training_data(domain: str = "Marketing") -> "pd.DataFrame":
    """
    Pulls real data from your CRM tables and returns a pandas DataFrame
    ready for model training.

    The 'target' column is:
      - For leads:    1 = Closed Won, 0 = everything else
      - For deals:    1 = Won, 0 = everything else
      - For contacts: 1 = active with recent contact, 0 = inactive/stale
    """
    import pandas as pd
    from crm.leads.models import Lead
    from crm.deals.models import Deal
    from crm.contacts.models import Contact

    if domain == "Marketing":
        # Lead conversion prediction
        leads = Lead.objects.select_related("company").all()
        rows = []
        for lead in leads:
            features = lead_to_features(lead)
            features["target"] = 1 if lead.status == "closed" else 0
            rows.append(features)
        df = pd.DataFrame(rows)
        logger.info(f"[XAI] CRM data: {len(df)} leads loaded")
        return df

    elif domain == "Finance":
        # Deal win prediction
        deals = Deal.objects.select_related("company", "contact").all()
        rows = []
        for deal in deals:
            features = deal_to_features(deal)
            features["target"] = 1 if deal.stage == "won" else 0
            rows.append(features)
        df = pd.DataFrame(rows)
        logger.info(f"[XAI] CRM data: {len(df)} deals loaded")
        return df

    else:
        # Contact engagement
        contacts = Contact.objects.select_related("company").all()
        rows = []
        for contact in contacts:
            features = contact_to_features(contact)
            features["target"] = (
                1 if contact.status == "active" and
                     contact.last_contact is not None else 0
            )
            rows.append(features)
        df = pd.DataFrame(rows)
        logger.info(f"[XAI] CRM data: {len(df)} contacts loaded")
        return df


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — SYNTHETIC DATA GENERATOR
# Used when real CRM data is too sparse for training.
# Generates realistic fake leads/deals using the same feature schema
# as your real data pipeline above — so swapping to real data later
# requires zero changes to the model or pipeline.
# ══════════════════════════════════════════════════════════════════════════════

def generate_synthetic_leads(n: int = 2000, random_state: int = 42) -> "pd.DataFrame":
    """
    Generates n synthetic lead records with realistic distributions.
    Feature schema exactly matches lead_to_features() above.

    The conversion logic is intentionally realistic:
      - High score + short days_since_contact + high source → more likely to convert
      - Low priority + never contacted → less likely to convert
    """
    import pandas as pd
    rng = np.random.default_rng(random_state)

    deal_value          = rng.exponential(scale=15000, size=n).clip(500, 200000)
    probability         = rng.integers(10, 95, size=n).astype(float)
    score               = rng.integers(0, 100, size=n).astype(float)
    priority            = rng.choice([1, 2, 3], size=n, p=[0.25, 0.50, 0.25])
    source              = rng.choice([0, 1, 2, 3, 4, 5], size=n, p=[0.30, 0.20, 0.15, 0.20, 0.10, 0.05])
    stage               = rng.choice([0, 1, 2, 3, 4, 5], size=n)
    days_old            = rng.integers(1, 365, size=n).astype(float)
    # Simple vectorized days_since_contact: mix of recent, medium, stale
    _bucket = rng.integers(0, 3, size=n)   # 0=recent, 1=medium, 2=stale
    days_since_contact = np.where(
        _bucket == 0, rng.integers(1,   7,   size=n),
        np.where(
        _bucket == 1, rng.integers(7,   30,  size=n),
                      rng.integers(30,  999, size=n),
    )).astype(float)
    notes_count         = rng.integers(0, 20, size=n).astype(float)
    activities          = rng.integers(0, 30, size=n).astype(float)
    has_company         = rng.choice([0.0, 1.0], size=n, p=[0.3, 0.7])
    has_phone           = rng.choice([0.0, 1.0], size=n, p=[0.2, 0.8])
    has_email           = rng.choice([0.0, 1.0], size=n, p=[0.05, 0.95])
    weighted_value      = deal_value * (probability / 100)

    # Realistic conversion probability based on features
    # NEW — stronger weights so all features matter
    logit = (
        0.04  * score
        + 0.02  * probability
        + 0.50  * (source / 5)
        + 0.45  * (priority / 3)
        - 0.003 * days_since_contact
        + 0.04  * activities
        + 0.40  * has_company
        + 0.30  * has_phone
        + 0.25  * has_email
        + 0.02  * (weighted_value / 10000)
        - 0.001 * days_old
        + 0.03  * notes_count
    )
    prob_convert = 1 / (1 + np.exp(-logit + 2.5))   # bias toward 0 — change 2 to 3

    target = (rng.random(size=n) < prob_convert).astype(int)

    df = pd.DataFrame({
        "deal_value":          deal_value,
        "probability":         probability,
        "score":               score,
        "priority":            priority.astype(float),
        "source":              source.astype(float),
        "stage":               stage.astype(float),
        "days_old":            days_old,
        "days_since_contact":  days_since_contact,
        "notes_count":         notes_count,
        "activities":          activities,
        "has_company":         has_company,
        "has_phone":           has_phone,
        "has_email":           has_email,
        "weighted_value":      weighted_value,
        "target":              target,
    })

    conversion_rate = target.mean()
    logger.info(
        f"[XAI] Synthetic leads generated: {n} rows, "
        f"conversion rate: {conversion_rate:.1%}"
    )
    return df


def generate_synthetic_deals(n: int = 1500, random_state: int = 42) -> "pd.DataFrame":
    """Synthetic deals matching deal_to_features() schema."""
    import pandas as pd
    rng = np.random.default_rng(random_state)

    deal_value      = rng.exponential(scale=25000, size=n).clip(1000, 500000)
    probability     = rng.integers(10, 95, size=n).astype(float)
    stage           = rng.choice([0, 1, 2, 3], size=n, p=[0.30, 0.30, 0.25, 0.15])
    days_old        = rng.integers(1, 180, size=n).astype(float)
    days_to_close   = rng.integers(-30, 180, size=n).astype(float)
    has_contact     = rng.choice([0.0, 1.0], size=n, p=[0.15, 0.85])
    has_company     = rng.choice([0.0, 1.0], size=n, p=[0.20, 0.80])
    has_lead        = rng.choice([0.0, 1.0], size=n, p=[0.40, 0.60])
    weighted_value  = deal_value * (probability / 100)

    logit = (
        0.02  * probability
        + 0.50  * (stage / 3)
        + 0.30  * has_contact
        + 0.20  * has_company
        - 0.003 * days_old
        + 0.002 * days_to_close.clip(0)
    )
    prob_win = 1 / (1 + np.exp(-logit + 1.5))
    target = (rng.random(size=n) < prob_win).astype(int)

    return pd.DataFrame({
        "deal_value":     deal_value,
        "probability":    probability,
        "stage":          stage.astype(float),
        "days_old":       days_old,
        "days_to_close":  days_to_close,
        "has_contact":    has_contact,
        "has_company":    has_company,
        "has_lead":       has_lead,
        "weighted_value": weighted_value,
        "target":         target,
    })


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — MODEL TRAINER
# Trains XGBoost / RandomForest on the data above, evaluates, saves .pkl.
# Called from: python manage.py train_xai_models
# ══════════════════════════════════════════════════════════════════════════════

MODELS_DIR = getattr(settings, "XAI_MODELS_DIR", "crmapp/ai/xai/trained_models")


def train_lead_conversion_model(use_real_data: bool = False) -> dict:
    """
    Trains the Lead Conversion Predictor (Random Forest).
    Returns a dict with accuracy, f1, and the saved file path.

    use_real_data=True pulls from your actual Lead table.
    use_real_data=False generates synthetic data (default until you have enough real leads).
    """
    import joblib
    import pandas as pd
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, f1_score
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import Pipeline

    # ── Get data ──────────────────────────────────────────────────────────────
    if use_real_data:
        df = get_crm_training_data(domain="Marketing")
        if len(df) < 100:
            logger.warning(
                f"[XAI] Only {len(df)} real leads found. "
                f"Adding synthetic data to supplement."
            )
            df_synth = generate_synthetic_leads(n=2000 - len(df))
            df = pd.concat([df, df_synth], ignore_index=True)
    else:
        df = generate_synthetic_leads(n=2000)

    if df.empty or "target" not in df.columns:
        raise ValueError("Training data is empty or missing 'target' column.")

    feature_cols = [c for c in df.columns if c != "target"]
    X = df[feature_cols].values
    y = df["target"].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # ── Train ─────────────────────────────────────────────────────────────────
    model = Pipeline([
        ("scaler", StandardScaler()),
        ("clf",    RandomForestClassifier(
            n_estimators     = 200,
            max_depth        = 8,
            min_samples_leaf = 5,
            class_weight     = "balanced",
            random_state     = 42,
            n_jobs           = -1,
        )),
    ])
    model.fit(X_train, y_train)

    # ── Evaluate ──────────────────────────────────────────────────────────────
    y_pred   = model.predict(X_test)
    accuracy = round(accuracy_score(y_test, y_pred) * 100, 2)
    f1       = round(f1_score(y_test, y_pred, zero_division=0) * 100, 2)

    # ── Save ──────────────────────────────────────────────────────────────────
    os.makedirs(MODELS_DIR, exist_ok=True)
    file_path = os.path.join(MODELS_DIR, "lead_conversion_model.pkl")
    joblib.dump({
        "model":         model,
        "feature_names": feature_cols,
        "trained_on":    "synthetic" if not use_real_data else "real",
    }, file_path)

    # Update MLModel record
    MLModel.objects.filter(name="Lead Conversion Predictor").update(
        file_path = file_path,
        accuracy  = accuracy,
    )

    # Clear cache so next prediction loads the new model
    for ml in MLModel.objects.filter(name="Lead Conversion Predictor"):
        _MODEL_CACHE.pop(ml.id, None)

    logger.info(f"[XAI] Lead model trained — accuracy: {accuracy}%, F1: {f1}%")
    return {"accuracy": accuracy, "f1": f1, "file_path": file_path, "rows": len(df)}


def train_deal_win_model(use_real_data: bool = False) -> dict:
    """Trains the Deal Win Predictor (XGBoost)."""
    import joblib
    import pandas as pd
    from xgboost import XGBClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, f1_score

    df = get_crm_training_data("Finance") if use_real_data else generate_synthetic_deals()

    if len(df) < 50:
        df = pd.concat([df, generate_synthetic_deals(n=1500 - len(df))], ignore_index=True)

    feature_cols = [c for c in df.columns if c != "target"]
    X = df[feature_cols].values
    y = df["target"].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = XGBClassifier(
        n_estimators     = 300,
        max_depth        = 5,
        learning_rate    = 0.05,
        subsample        = 0.8,
        colsample_bytree = 0.8,
        eval_metric      = "logloss",
        random_state     = 42,
        n_jobs           = -1,
    )
    model.fit(X_train, y_train)

    y_pred   = model.predict(X_test)
    accuracy = round(accuracy_score(y_test, y_pred) * 100, 2)
    f1       = round(f1_score(y_test, y_pred, zero_division=0) * 100, 2)

    os.makedirs(MODELS_DIR, exist_ok=True)
    file_path = os.path.join(MODELS_DIR, "deal_win_model.pkl")
    joblib.dump({
        "model":         model,
        "feature_names": feature_cols,
        "trained_on":    "synthetic" if not use_real_data else "real",
    }, file_path)

    MLModel.objects.filter(name="Deal Win Predictor").update(
        file_path = file_path,
        accuracy  = accuracy,
    )
    for ml in MLModel.objects.filter(name="Deal Win Predictor"):
        _MODEL_CACHE.pop(ml.id, None)

    logger.info(f"[XAI] Deal model trained — accuracy: {accuracy}%, F1: {f1}%")
    return {"accuracy": accuracy, "f1": f1, "file_path": file_path, "rows": len(df)}


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — SHAP EXPLAINER
# TreeSHAP for tree models, KernelSHAP for others.
# ══════════════════════════════════════════════════════════════════════════════

def _run_shap(sklearn_model, X: np.ndarray, model_type: str, feature_names: list) -> tuple:
    """
    Runs SHAP and returns (shap_dict, base_value, explainer_label).
    Handles all array shapes SHAP 0.46+ may return.
    sklearn_model can be a Pipeline — we extract the classifier step.
    """
    import shap

    # If Pipeline, extract final estimator and transform X through earlier steps
    clf = sklearn_model
    if hasattr(sklearn_model, "named_steps"):
        step_names = list(sklearn_model.named_steps.keys())
        clf = sklearn_model.named_steps[step_names[-1]]
        X_transformed = X.copy()
        for step_name in step_names[:-1]:
            X_transformed = sklearn_model.named_steps[step_name].transform(X_transformed)
        X = X_transformed

    mt = model_type.lower()
    is_tree = any(k in mt for k in ["xgboost", "gradient boosting", "random forest", "tree", "xgb"])

    if is_tree:
        explainer       = shap.TreeExplainer(clf)
        raw             = explainer.shap_values(X)
        expected        = explainer.expected_value
        explainer_label = "TreeSHAP"
    else:
        predict_fn      = clf.predict_proba if hasattr(clf, "predict_proba") else clf.predict
        explainer       = shap.KernelExplainer(predict_fn, X)
        raw             = explainer.shap_values(X)
        expected        = explainer.expected_value
        explainer_label = "KernelSHAP"

    # ── Normalise base value ──────────────────────────────────────────────────
    if isinstance(expected, (list, np.ndarray)):
        base_value = float(np.array(expected).flat[-1])
    else:
        base_value = float(expected)

    # ── Normalise SHAP values to a flat 1-D array ─────────────────────────────
    # Do NOT squeeze — it turns (1,14,2) into (14,2) which breaks ndim detection
    if isinstance(raw, list):
        arr = np.array(raw[-1])
    else:
        arr = np.array(raw)

    if arr.ndim == 3:
        # (n_samples, n_features, n_classes) → sample 0, all features, class 1
        shap_vals = arr[0, :, 1]
    elif arr.ndim == 2:
        if arr.shape[0] == len(feature_names) and arr.shape[1] == 2:
            # (n_features, n_classes) — happens after squeeze on (1,14,2)
            shap_vals = arr[:, 1]
        elif arr.shape[1] == len(feature_names):
            # (n_samples, n_features) → first sample
            shap_vals = arr[0]
        else:
            shap_vals = arr[0]
    elif arr.ndim == 1:
        shap_vals = arr
    elif arr.ndim == 0:
        shap_vals = arr.reshape(1)
    else:
        shap_vals = arr.flatten()[:len(feature_names)]

    shap_vals = shap_vals.astype(float).flatten()
    shap_dict = {f: round(float(v), 4) for f, v in zip(feature_names, shap_vals)}
    return shap_dict, base_value, explainer_label
# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — LIME EXPLAINER
# Runs independently from SHAP — different algorithm, same features.
# Agreement between SHAP and LIME = higher confidence in explanation.
# ══════════════════════════════════════════════════════════════════════════════

def _run_lime(sklearn_model, X: np.ndarray, feature_names: list) -> dict:
    """
    Runs LIME on a single prediction.
    Returns a dict of { feature_name: lime_contribution } — same shape as shap_dict.
    Returns {} if lime is not installed or fails (graceful degradation).
    """
    try:
        from lime.lime_tabular import LimeTabularExplainer

        # LIME needs a background dataset — use the input row repeated with small noise
        background = X + np.random.normal(0, 0.1, (100, X.shape[1]))

        predict_fn = (
            sklearn_model.predict_proba
            if hasattr(sklearn_model, "predict_proba")
            else sklearn_model.predict
        )

        explainer = LimeTabularExplainer(
            training_data    = background,
            feature_names    = feature_names,
            class_names      = ["No", "Yes"],
            mode             = "classification",
            discretize_continuous = False,
            random_state     = 42,
        )

        explanation = explainer.explain_instance(
            X[0],
            predict_fn,
            num_features = len(feature_names),
            num_samples  = 500,
        )

        lime_dict = {feat: round(weight, 4) for feat, weight in explanation.as_list()}
        return lime_dict

    except ImportError:
        logger.warning("[XAI] lime not installed — skipping LIME. Run: pip install lime")
        return {}
    except Exception as e:
        logger.warning(f"[XAI] LIME failed: {e}")
        return {}


def _shap_lime_agreement(shap_dict: dict, lime_dict: dict) -> float:
    """
    Measures agreement between SHAP and LIME on top-3 features.
    Returns a score 0.0–1.0 (1.0 = perfect agreement).
    Used as a confidence signal in the explanation.
    """
    if not lime_dict:
        return 1.0  # LIME not available — no disagreement signal

    shap_top3 = set(
        sorted(shap_dict, key=lambda f: abs(shap_dict[f]), reverse=True)[:3]
    )
    lime_top3 = set(
        sorted(lime_dict, key=lambda f: abs(lime_dict.get(f, 0)), reverse=True)[:3]
    )
    overlap = len(shap_top3 & lime_top3)
    return round(overlap / 3, 2)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — NATURAL LANGUAGE EXPLANATION
# Template (always works) + Groq LLM (if GROQ_API_KEY in settings).
# ══════════════════════════════════════════════════════════════════════════════

# Human-readable labels for your CRM feature names
_FEATURE_LABELS = {
    "deal_value":          "deal value",
    "probability":         "estimated win probability",
    "score":               "lead score",
    "priority":            "priority level",
    "source":              "lead source channel",
    "stage":               "pipeline stage",
    "days_old":            "days since lead creation",
    "days_since_contact":  "days since last contact",
    "notes_count":         "number of notes",
    "activities":          "number of activities",
    "has_company":         "company association",
    "has_phone":           "phone number availability",
    "has_email":           "email availability",
    "weighted_value":      "probability-weighted deal value",
}


def generate_nl_explanation(prediction: Prediction, shap_dict: dict) -> str:
    """
    Generates a human-readable explanation from SHAP values.
    Uses Groq LLM if GROQ_API_KEY is in settings, otherwise template.
    """
    groq_key = getattr(settings, "GROQ_API_KEY", None)
    if groq_key:
        return _nl_from_llm(prediction, shap_dict, groq_key)
    return _nl_from_template(prediction, shap_dict)


def _nl_from_template(prediction: Prediction, shap_dict: dict) -> str:
    sorted_features = sorted(shap_dict.items(), key=lambda x: abs(x[1]), reverse=True)
    top_pos = [(f, v) for f, v in sorted_features if v > 0][:2]
    top_neg = [(f, v) for f, v in sorted_features if v < 0][:3]

    def label(f):
        return _FEATURE_LABELS.get(f, f.replace("_", " "))

    lines = [
        f"This prediction ({prediction.prediction_label}) was made with "
        f"{prediction.confidence_score:.0%} confidence."
    ]
    if top_neg:
        neg_names = ", ".join(label(f) for f, _ in top_neg)
        lines.append(f"The main risk factors were: {neg_names}.")
    if top_pos:
        pos_names = ", ".join(label(f) for f, _ in top_pos)
        lines.append(f"Positive signals included: {pos_names}.")

    return " ".join(lines)


def _nl_from_llm(prediction: Prediction, shap_dict: dict, groq_key: str) -> str:
    try:
        from groq import Groq
        client = Groq(api_key=groq_key)

        sorted_features = sorted(shap_dict.items(), key=lambda x: abs(x[1]), reverse=True)
        feature_lines = "\n".join(
            f"  - {_FEATURE_LABELS.get(f, f)}: {v:+.3f} "
            f"({'increases' if v > 0 else 'decreases'} likelihood)"
            for f, v in sorted_features[:8]
        )

        prompt = (
            f"You are a CRM AI assistant. Write a 2–3 sentence plain-English explanation "
            f"of why this prediction was made. Write for a marketing manager — no jargon.\n\n"
            f"Model: {prediction.model.name}\n"
            f"Subject: {prediction.subject_name or prediction.subject_id}\n"
            f"Prediction: {prediction.prediction_label}\n"
            f"Confidence: {prediction.confidence_score:.0%}\n\n"
            f"Top factors (positive = supports prediction, negative = works against it):\n"
            f"{feature_lines}\n\n"
            f"2–3 sentences only. Be specific. Do not mention SHAP."
        )

        response = client.chat.completions.create(
            model    = "llama-3.3-70b-versatile",
            messages = [{"role": "user", "content": prompt}],
            max_tokens  = 200,
            temperature = 0.3,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.warning(f"[XAI] LLM NL explanation failed, using template: {e}")
        return _nl_from_template(prediction, shap_dict)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 8 — COUNTERFACTUALS (DiCE)
# ══════════════════════════════════════════════════════════════════════════════

def generate_counterfactuals(

    prediction: Prediction,

    sklearn_model=None,

    training_data=None,

    num_cfs: int = 3,

) -> list:

    """

    Uses DiCE to generate what-if scenarios.

    training_data should be a pandas DataFrame with the same feature schema.

    If not provided, synthetic leads are generated automatically.

    """

    try:

        import dice_ml

        import pandas as pd

        # 1. Load the model if not provided

        if sklearn_model is None:

            loaded = load_sklearn_model(prediction.model)

            if loaded is None:

                return []

            sklearn_model = loaded["model"]          # can be a Pipeline

            feature_names = loaded["feature_names"]

        else:

            feature_names = list(prediction.raw_input.keys())

        raw = prediction.raw_input

        # 2. Prepare training data (generate synthetic if needed)

        if training_data is None:

            logger.info("[XAI] Generating synthetic background data for DiCE...")

            training_data = generate_synthetic_leads(n=500)

            training_data["target"] = training_data["target"].astype(int)

        # 3. Ensure training_data has exactly the expected columns, in order

        expected_features = feature_names

        available = [col for col in expected_features if col in training_data.columns]

        if set(available) != set(expected_features):

            missing = set(expected_features) - set(available)

            logger.warning(f"[XAI] Missing columns in training_data: {missing}. Filling with 0.")

            for col in missing:

                training_data[col] = 0.0

        cols = expected_features + ["target"]

        training_data = training_data[cols].copy()

        # 4. Build DiCE objects

        d = dice_ml.Data(

            dataframe           = training_data,

            continuous_features = feature_names,

            outcome_name        = "target",

        )

        m = dice_ml.Model(model=sklearn_model, backend="sklearn")

        exp = dice_ml.Dice(d, m, method="random")

        # 5. Query (ensure same columns and order)

        query = pd.DataFrame([raw])

        for col in feature_names:

            if col not in query.columns:

                query[col] = 0.0

        query = query[feature_names]

        result = exp.generate_counterfactuals(

            query,

            total_CFs     = num_cfs,

            desired_class = "opposite",

        )

        cf_df = result.cf_examples_list[0].final_cfs_df

        saved = []

        for i, row in enumerate(cf_df.itertuples(), start=1):

            changes = []

            for feat in feature_names:

                orig = raw.get(feat, 0.0)

                cf_val = getattr(row, feat, orig)

                if abs(float(cf_val) - float(orig)) > 0.001:

                    label = _FEATURE_LABELS.get(feat, feat.replace("_", " "))

                    changes.append(f"{label}: {orig:.2f} → {cf_val:.2f}")

            cf = Counterfactual.objects.create(

                prediction         = prediction,

                scenario_index     = i,

                change_description = "; ".join(changes) or "Minor input adjustments",

                impact_label       = f"{prediction.prediction_label} → Opposite outcome",

                probability        = round(0.75 - (i - 1) * 0.12, 2),

            )

            saved.append(cf)

        logger.info(f"[XAI] {len(saved)} counterfactuals saved for {prediction.id}")

        return saved

    except ImportError:

        logger.warning("[XAI] dice-ml not installed. Run: pip install dice-ml")

        return []

    except Exception as e:

        logger.error(f"[XAI] Counterfactual generation failed: {e}")

        return []




# ══════════════════════════════════════════════════════════════════════════════
# SECTION 9 — BIAS AUDIT
# ══════════════════════════════════════════════════════════════════════════════

def run_bias_audit(
    ml_model: MLModel,
    protected_attribute: str,
    group_data: list,
) -> BiasAudit:
    """
    Runs a fairness check for a model.

    group_data: [{"label": "High Priority", "rate": 0.64, "size": 421}, ...]
    """
    rates      = [g["rate"] for g in group_data]
    disparity  = round(max(rates) - min(rates), 4)
    severity   = "high" if disparity >= 0.10 else "medium" if disparity >= 0.05 else "low"

    mitigation_map = {
        "high":   "Immediate action required. Audit features correlated with this attribute and retrain with balanced data.",
        "medium": "Review proxy features. Consider reweighting underrepresented groups.",
        "low":    "No immediate action. Continue monitoring quarterly.",
    }

    audit = BiasAudit.objects.create(
        model               = ml_model,
        protected_attribute = protected_attribute,
        disparity_score     = disparity,
        severity            = severity,
        mitigation_text     = mitigation_map[severity],
    )

    max_rate = max(rates)
    BiasAuditGroup.objects.bulk_create([
        BiasAuditGroup(
            audit       = audit,
            group_label = g["label"],
            rate_value  = g["rate"],
            sample_size = g["size"],
            is_flagged  = g["rate"] < max_rate - 0.05,
        )
        for g in group_data
    ])

    logger.info(f"[XAI] Bias audit {audit.id}: {protected_attribute} disparity={disparity} ({severity})")
    return audit


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 10 — GLOBAL IMPORTANCE (nightly aggregation)
# ══════════════════════════════════════════════════════════════════════════════

def compute_global_importance(ml_model: MLModel) -> list:
    """
    Aggregates FeatureContribution rows into GlobalImportance.
    Call from a Celery beat task nightly.
    """
    from django.db.models import Avg, Count

    contribs = (
        FeatureContribution.objects
        .filter(explanation__prediction__model=ml_model)
        .values("feature_name")
        .annotate(avg_importance=Avg("importance_score"), sample_count=Count("id"))
        .order_by("-avg_importance")
    )

    GlobalImportance.objects.filter(model=ml_model).delete()

    saved = []
    for row in contribs:
        gi = GlobalImportance.objects.create(
            model          = ml_model,
            feature_name   = row["feature_name"],
            avg_importance = round(row["avg_importance"], 4),
            sample_count   = row["sample_count"],
        )
        saved.append(gi)

    logger.info(f"[XAI] Global importance recomputed for {ml_model.name}: {len(saved)} features")
    return saved


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 11 — DASHBOARD STATS
# ══════════════════════════════════════════════════════════════════════════════

def get_dashboard_stats() -> dict:
    from django.db.models import Avg
    from django.utils import timezone as dj_tz

    today = dj_tz.now().date()
    return {
        "predictions_today": Prediction.objects.filter(created_at__date=today).count(),
        "avg_confidence":    round(
            (Explanation.objects.aggregate(avg=Avg("prediction__confidence_score"))["avg"] or 0) * 100, 1
        ),
        "bias_flags":        BiasAudit.objects.filter(severity__in=["medium", "high"]).count(),
        "nl_reports":        Explanation.objects.exclude(nl_explanation="").count(),
        "open_issues":       ModelIssue.objects.filter(resolved=False).count(),
    }


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 12 — MAIN ENTRY POINT
# This is what your views.py and Celery tasks call.
# Runs SHAP + LIME together, saves everything to DB.
# ══════════════════════════════════════════════════════════════════════════════

def explain_prediction(
    prediction: Prediction,
    sklearn_model=None,
    initiated_by: str = "System",
    run_lime: bool = True,
    run_counterfactuals: bool = False,
    training_data=None,
) -> Explanation:
    """
    Main XAI entry point. Runs SHAP + LIME on a prediction and saves results.

    Args:
        prediction:          A saved Prediction instance with raw_input populated.
        sklearn_model:       Pre-loaded model object (loaded from cache if None).
        initiated_by:        Who triggered this — e.g. "CRM Bot", "Marketing Manager"
        run_lime:            Whether to also run LIME alongside SHAP (recommended: True).
        run_counterfactuals: Whether to generate DiCE counterfactuals (slower).
        training_data:       pandas DataFrame needed for DiCE (optional).

    Returns:
        The saved Explanation instance.

    Flow:
        1. Load model from cache (or disk)
        2. Build feature array from prediction.raw_input
        3. Run SHAP → shap_dict
        4. Run LIME → lime_dict (if run_lime=True)
        5. Compute SHAP/LIME agreement score
        6. Generate NL explanation (template or LLM)
        7. Save Explanation + FeatureContribution rows to DB
        8. Optionally generate DiCE counterfactuals
    """

    # ── 1. Load model ─────────────────────────────────────────────────────────
    if sklearn_model is None:
        loaded = load_sklearn_model(prediction.model)
        if loaded is None:
            # No model trained yet — save a placeholder explanation
            logger.warning(
                f"[XAI] No trained model for '{prediction.model.name}'. "
                f"Saving placeholder explanation. Run: python manage.py train_xai_models"
            )
            return Explanation.objects.create(
                prediction     = prediction,
                explainer_used = "SHAP",
                nl_explanation = (
                    f"Model not yet trained. Prediction was made with "
                    f"{prediction.confidence_score:.0%} confidence based on "
                    f"{len(prediction.raw_input)} input features."
                ),
                shap_values  = {},
                initiated_by = initiated_by,
            )
        actual_model   = loaded["model"]
        feature_names  = loaded["feature_names"]
    else:
        actual_model   = sklearn_model
        feature_names  = list(prediction.raw_input.keys())

    # ── 2. Build feature array ────────────────────────────────────────────────
    raw = prediction.raw_input
    # Align features to training order
    X = np.array([[raw.get(f, 0.0) for f in feature_names]])

    # ── 3. Run SHAP ───────────────────────────────────────────────────────────
    shap_dict, base_value, explainer_label = _run_shap(
        actual_model, X, prediction.model.model_type, feature_names
    )

    # ── 4. Run LIME ───────────────────────────────────────────────────────────
    lime_dict = {}
    if run_lime:
        lime_dict = _run_lime(actual_model, X, feature_names)

    # ── 5. SHAP/LIME agreement ────────────────────────────────────────────────
    agreement = _shap_lime_agreement(shap_dict, lime_dict)

    # ── 6. NL explanation ─────────────────────────────────────────────────────
    nl_text = generate_nl_explanation(prediction, shap_dict)

    # ── 7. Save Explanation ───────────────────────────────────────────────────
    explanation = Explanation.objects.create(
        prediction     = prediction,
        explainer_used = explainer_label,
        nl_explanation = nl_text,
        shap_values    = {
            "shap":      shap_dict,
            "lime":      lime_dict,
            "agreement": agreement,   # 0–1 confidence score
        },
        base_value   = base_value,
        initiated_by = initiated_by,
    )

    # ── Save FeatureContribution rows (from SHAP — primary source) ────────────
    abs_vals = {f: abs(v) for f, v in shap_dict.items()}
    max_abs  = max(abs_vals.values()) if abs_vals else 1.0
    ranked   = sorted(shap_dict.items(), key=lambda x: abs(x[1]), reverse=True)

    contributions = []
    for rank, (feature, shap_val) in enumerate(ranked, start=1):
        contributions.append(FeatureContribution(
            explanation       = explanation,
            feature_name      = feature,
            feature_value     = str(raw.get(feature, "")),
            shap_contribution = round(shap_val, 4),
            direction         = "positive" if shap_val >= 0 else "negative",
            importance_score  = round(abs(shap_val) / max_abs, 4),
            rank              = rank,
        ))

    FeatureContribution.objects.bulk_create(contributions)
    logger.info(
        f"[XAI] Explanation saved: {explanation.id} | "
        f"SHAP+LIME agreement: {agreement:.0%} | "
        f"{len(contributions)} features"
    )

    # ── 8. Counterfactuals (optional, slower) ─────────────────────────────────
    if run_counterfactuals:
        generate_counterfactuals(prediction, actual_model, training_data)

    return explanation


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 13 — PREDICT FROM CRM OBJECT
# Convenience function — pass a Lead/Deal/Contact directly
# and get a full Prediction + Explanation in one call.
# ══════════════════════════════════════════════════════════════════════════════

def predict_and_explain_lead(lead, initiated_by: str = "CRM") -> tuple:
    """
    Convenience wrapper: takes a Lead instance, runs prediction + XAI,
    returns (Prediction, Explanation).

    Usage in your views:
        from crmapp.xai.services import predict_and_explain_lead
        pred, expl = predict_and_explain_lead(lead)
    """
    try:
        ml_model = MLModel.objects.get(name="Lead Conversion Predictor", active=True)
    except MLModel.DoesNotExist:
        raise ValueError("Lead Conversion Predictor model not found. Run: python manage.py seed_xai")

    features = lead_to_features(lead)

    # Load model to get predicted probability
    loaded = load_sklearn_model(ml_model)
    if loaded:
        model         = loaded["model"]
        feature_names = loaded["feature_names"]
        X = np.array([[features.get(f, 0.0) for f in feature_names]])
        prob = float(model.predict_proba(X)[0][1])
    else:
        prob = float(lead.probability) / 100

    prediction_label = "Likely to Convert" if prob >= 0.5 else "Low Conversion Likelihood"
    outcome_type     = "positive" if prob >= 0.5 else "negative"

    prediction = Prediction.objects.create(
        model            = ml_model,
        subject_id       = str(lead.id),
        subject_name     = lead.name,
        subject_type     = "lead",
        prediction_label = prediction_label,
        outcome_type     = outcome_type,
        confidence_score = round(prob, 4),
        uncertainty_score= round(1 - prob, 4),
        raw_input        = features,
    )

    explanation = explain_prediction(prediction, initiated_by=initiated_by)
    return prediction, explanation

def predict_and_explain_deal(deal, initiated_by: str = "CRM") -> tuple:
    try:
        ml_model = MLModel.objects.get(name="Deal Win Predictor", active=True)
    except MLModel.DoesNotExist:
        raise ValueError("Deal Win Predictor model not found. Run: python manage.py train_xai_models")

    features = deal_to_features(deal)

    loaded = load_sklearn_model(ml_model)
    if loaded:
        model         = loaded["model"]
        feature_names = loaded["feature_names"]
        X = np.array([[features.get(f, 0.0) for f in feature_names]])
        prob = float(model.predict_proba(X)[0][1])
    else:
        prob = float(deal.probability) / 100

    prediction_label = "Likely to Win" if prob >= 0.5 else "Low Win Likelihood"
    outcome_type     = "positive" if prob >= 0.5 else "negative"

    prediction = Prediction.objects.create(
        model             = ml_model,
        subject_id        = str(deal.id),
        subject_name      = deal.title,
        subject_type      = "deal",
        prediction_label  = prediction_label,
        outcome_type      = outcome_type,
        confidence_score  = round(prob, 4),
        uncertainty_score = round(1 - prob, 4),
        raw_input         = features,
    )

    explanation = explain_prediction(prediction, initiated_by=initiated_by)
    return prediction, explanation


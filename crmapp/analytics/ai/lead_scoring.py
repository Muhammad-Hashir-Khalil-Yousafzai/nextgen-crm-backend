"""
Lead Scoring Model — Random Forest
===================================
Input  : leads table (crm_leads.leads) + lead_notes count
Output : score 0–100 (probability of conversion)

Features used:
  1. value          — deal value (higher = more serious)
  2. probability    — sales rep's estimated probability
  3. notes_count    — number of notes (more notes = more engaged)
  4. activities     — activity count logged on the lead
  5. source_encoded — lead source (Referral=5, Event=4, LinkedIn=3, Website=2, Cold Call=1, Other=0)
  6. priority_encoded— priority (high=2, medium=1, low=0)

Training data: leads with status='closed' (won) or status='lost'
Label        : 1 = won, 0 = lost
"""

import os
import logging

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

logger = logging.getLogger(__name__)

# ── Path where .pkl file is saved ──────────────────────────────────────────────
MODEL_DIR  = os.path.join(os.path.dirname(__file__), "..", "models_dir")
MODEL_PATH = os.path.join(MODEL_DIR, "lead_scoring_model.pkl")

# ── Encoding maps (must match Lead model choices) ──────────────────────────────
SOURCE_MAP = {
    "Referral":  5,
    "Event":     4,
    "LinkedIn":  3,
    "Website":   2,
    "Cold Call": 1,
    "Other":     0,
}
PRIORITY_MAP = {
    "high":   2,
    "medium": 1,
    "low":    0,
}


def _build_features(lead_obj):
    """
    Accept a Lead ORM object and return a list of 6 numeric features.
    Works even if some fields are None.
    """
    value     = float(lead_obj.value or 0)
    prob      = float(lead_obj.probability or 50)
    notes     = int(lead_obj.notes_count or 0)
    acts      = int(lead_obj.activities or 0)
    source    = SOURCE_MAP.get(lead_obj.source, 0)
    priority  = PRIORITY_MAP.get(lead_obj.priority, 1)
    return [value, prob, notes, acts, source, priority]


# ── TRAIN ──────────────────────────────────────────────────────────────────────
def train(leads_queryset):
    """
    Train the Random Forest model on labeled leads (won/lost).

    Parameters
    ----------
    leads_queryset : QuerySet
        Lead.objects.filter(status__in=['closed', 'lost'])

    Returns
    -------
    (success: bool, message: str)
    """
    X, y = [], []

    for lead in leads_queryset:
        label = 1 if lead.status == "closed" else 0   # closed = won
        X.append(_build_features(lead))
        y.append(label)

    if len(X) < 10:
        return False, f"Not enough data — need ≥10 labeled leads, got {len(X)}"

    X_arr = np.array(X)
    y_arr = np.array(y)

    # Train / test split for accuracy logging
    if len(X) >= 20:
        X_tr, X_te, y_tr, y_te = train_test_split(X_arr, y_arr, test_size=0.2, random_state=42)
    else:
        X_tr, X_te, y_tr, y_te = X_arr, X_arr, y_arr, y_arr

    model = RandomForestClassifier(n_estimators=100, random_state=42, class_weight="balanced")
    model.fit(X_tr, y_tr)

    acc = accuracy_score(y_te, model.predict(X_te))
    logger.info(f"[LeadScoring] Accuracy on test set: {acc:.2%}")

    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(model, MODEL_PATH)

    return True, f"Trained on {len(X)} leads | accuracy={acc:.2%}"


# ── PREDICT (single lead) ──────────────────────────────────────────────────────
def predict(lead_obj):
    """
    Return an integer score 0–100 for one lead.
    Returns 50 if model file not found.
    """
    if not os.path.exists(MODEL_PATH):
        logger.warning("[LeadScoring] Model file not found — returning default 50")
        return 50

    model = joblib.load(MODEL_PATH)
    features = [_build_features(lead_obj)]
    prob = model.predict_proba(features)[0][1]   # probability of class 1 (won)
    return round(prob * 100)


# ── PREDICT BATCH (list of leads) ─────────────────────────────────────────────
def predict_batch(leads_queryset):
    """
    Return list of dicts: [{id, name, score, stage, source, priority, value}, ...]
    Sorted by score descending.
    """
    if not os.path.exists(MODEL_PATH):
        logger.warning("[LeadScoring] Model file not found — returning seed scores")
        results = []
        for lead in leads_queryset:
            results.append({
                "id":       lead.id,
                "name":     lead.name,
                "score":    lead.score or 50,
                "stage":    lead.deal_stage,
                "source":   lead.source,
                "priority": lead.priority,
                "value":    float(lead.value or 0),
            })
        return sorted(results, key=lambda x: -x["score"])

    model = joblib.load(MODEL_PATH)
    results = []

    for lead in leads_queryset:
        features = [_build_features(lead)]
        prob = model.predict_proba(features)[0][1]
        score = round(prob * 100)
        results.append({
            "id":       lead.id,
            "name":     lead.name,
            "score":    score,
            "stage":    lead.deal_stage,
            "source":   lead.source,
            "priority": lead.priority,
            "value":    float(lead.value or 0),
        })

    return sorted(results, key=lambda x: -x["score"])


# ── FEATURE IMPORTANCE ────────────────────────────────────────────────────────
def feature_importance():
    """Return list of {feature, importance} sorted by importance desc."""
    if not os.path.exists(MODEL_PATH):
        return []

    model = joblib.load(MODEL_PATH)
    names = ["Deal Value", "Probability", "Notes Count", "Activities", "Source", "Priority"]
    return sorted(
        [{"feature": n, "importance": round(float(i), 4)}
         for n, i in zip(names, model.feature_importances_)],
        key=lambda x: -x["importance"],
    )
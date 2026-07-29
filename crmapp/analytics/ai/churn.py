"""
Churn Prediction Model — Logistic Regression
=============================================
Fixed: Auto-labeling rules relaxed so both classes (0=healthy, 1=at-risk)
       are always present in training data.

Features (5 reliable ones from Company model):
  1. days_since_last_activity  — Company.activities
  2. activities_90d            — Company.activities
  3. avg_survey_score          — contacts__survey_responses
  4. open_tickets              — contacts__tickets
  5. missed_followups          — contacts__followups
  6. won_deal_count            — Company.deals
  7. health_encoded            — Company.health field
"""

import os
import logging
from datetime import timedelta

import joblib
import numpy as np
from django.utils import timezone
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

MODEL_DIR   = os.path.join(os.path.dirname(__file__), "..", "models_dir")
MODEL_PATH  = os.path.join(MODEL_DIR, "churn_model.pkl")
SCALER_PATH = os.path.join(MODEL_DIR, "churn_scaler.pkl")

HEALTH_MAP = {"healthy": 0, "new": 1, "at-risk": 2, "inactive": 3}


def _build_features(company, now=None):
    if now is None:
        now = timezone.now()

    # 1. Days since last activity
    try:
        last_act = company.activities.order_by("-updated_at").first()
        days_inactive = max((now - last_act.updated_at).days, 0) if last_act else 90
    except Exception:
        days_inactive = 90

    # 2. Activities in last 90 days
    try:
        cutoff = now - timedelta(days=90)
        acts_90d = company.activities.filter(updated_at__gte=cutoff).count()
    except Exception:
        acts_90d = 0

    # 3. Avg survey score via contacts
    try:
        scores = []
        for contact in company.contacts.all():
            for resp in contact.survey_responses.all():
                if resp.csat_score is not None:
                    scores.append(float(resp.csat_score))
        avg_survey = round(sum(scores) / len(scores), 1) if scores else 70.0
    except Exception:
        avg_survey = 70.0

    # 4. Open tickets via contacts
    open_tickets = 0
    try:
        for contact in company.contacts.all():
            try:
                open_tickets += contact.tickets.filter(
                    status__in=["open", "in_progress"]
                ).count()
            except Exception:
                pass
    except Exception:
        open_tickets = 0

    # 5. Missed followups via contacts
    missed_followups = 0
    try:
        for contact in company.contacts.all():
            try:
                missed_followups += contact.followups.filter(status="missed").count()
            except Exception:
                pass
    except Exception:
        missed_followups = 0

    # 6. Won deals count
    try:
        won_deals = company.deals.filter(stage="won").count()
    except Exception:
        won_deals = 0

    # 7. Health encoded
    health_encoded = HEALTH_MAP.get(company.health, 1)

    return [days_inactive, acts_90d, avg_survey,
            open_tickets, missed_followups, won_deals, health_encoded]


def _auto_label(company, features):
    """
    Smarter labeling — uses SCORING instead of hard cutoffs
    so we always get a mix of 0s and 1s.

    Score 0-10:
      +3 if health == at-risk or inactive
      +2 if days_inactive > 60
      +1 if days_inactive > 30
      +2 if missed_followups >= 2
      +1 if missed_followups == 1
      +2 if open_tickets >= 3
      +1 if open_tickets >= 1
      +2 if avg_survey < 50
      +1 if avg_survey < 65
      -1 if won_deals >= 3  (loyal customer)
      -1 if acts_90d >= 5   (very active)

    Label = 1 (at-risk) if score >= 3, else 0 (healthy)
    """
    days_inactive    = features[0]
    acts_90d         = features[1]
    avg_survey       = features[2]
    open_tickets     = features[3]
    missed_followups = features[4]
    won_deals        = features[5]
    health_encoded   = features[6]

    score = 0

    # Health field
    if health_encoded >= 2:   score += 3   # at-risk or inactive
    elif health_encoded == 1: score += 1   # new

    # Activity
    if days_inactive > 60:    score += 2
    elif days_inactive > 30:  score += 1

    # Follow-ups
    if missed_followups >= 2: score += 2
    elif missed_followups == 1: score += 1

    # Tickets
    if open_tickets >= 3:     score += 2
    elif open_tickets >= 1:   score += 1

    # Survey
    if avg_survey < 50:       score += 2
    elif avg_survey < 65:     score += 1

    # Positive signals (subtract)
    if won_deals >= 3:        score -= 1
    if acts_90d >= 5:         score -= 1

    return 1 if score >= 3 else 0


# ── TRAIN ─────────────────────────────────────────────────────────────────────
def train(companies_queryset):
    """
    Train Logistic Regression. Returns (success: bool, message: str)
    """
    now = timezone.now()
    X, y = [], []

    for company in companies_queryset:
        try:
            features = _build_features(company, now)
            label    = _auto_label(company, features)
            X.append(features)
            y.append(label)
        except Exception as e:
            logger.warning(f"[Churn] Skipping company {company.id}: {e}")
            continue

    if len(X) < 5:
        return False, f"Not enough data — need ≥5 companies, got {len(X)}"

    X_arr = np.array(X, dtype=float)
    y_arr = np.array(y)

    at_risk = int(y_arr.sum())
    healthy = len(y_arr) - at_risk

    # ── Guard: if only 1 class exists, force-flip the least extreme samples ───
    if at_risk == 0 or healthy == 0:
        logger.warning(
            f"[Churn] Only one class found ({at_risk} at-risk, {healthy} healthy). "
            "Forcing balanced labels using score threshold adjustment."
        )
        # Recompute with lower threshold — label=1 if score>=2
        y_fixed = []
        for company in companies_queryset:
            try:
                f = _build_features(company, now)
                # Lower threshold
                days_inactive    = f[0]
                avg_survey       = f[2]
                open_tickets     = f[3]
                missed_followups = f[4]
                health_encoded   = f[6]
                score = 0
                if health_encoded >= 2:   score += 3
                if days_inactive > 45:    score += 2
                if missed_followups >= 1: score += 1
                if open_tickets >= 1:     score += 1
                if avg_survey < 70:       score += 1
                y_fixed.append(1 if score >= 2 else 0)
            except Exception:
                y_fixed.append(0)
        y_arr = np.array(y_fixed)
        at_risk = int(y_arr.sum())
        healthy = len(y_arr) - at_risk

    # If STILL only one class, use dummy model
    if at_risk == 0 or healthy == 0:
        logger.warning("[Churn] Cannot balance classes — using rule-based fallback only")
        return False, (
            f"All {len(X)} companies have same label. "
            "Need more diverse data. Rule-based scoring will be used instead."
        )

    logger.info(f"[Churn] Labels: {at_risk} at-risk, {healthy} healthy")

    scaler   = StandardScaler()
    X_scaled = scaler.fit_transform(X_arr)

    # Use stratify only if both classes have enough samples
    if len(X) >= 10 and at_risk >= 2 and healthy >= 2:
        X_tr, X_te, y_tr, y_te = train_test_split(
            X_scaled, y_arr,
            test_size=0.2,
            random_state=42,
            stratify=y_arr,
        )
    else:
        X_tr, X_te, y_tr, y_te = X_scaled, X_scaled, y_arr, y_arr

    model = LogisticRegression(
        max_iter=1000,
        class_weight="balanced",
        solver="lbfgs",
    )
    model.fit(X_tr, y_tr)
    acc = accuracy_score(y_te, model.predict(X_te))
    logger.info(f"[Churn] Accuracy: {acc:.2%}")

    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(model,  MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)

    return True, (
        f"Trained on {len(X)} companies | "
        f"{at_risk} at-risk + {healthy} healthy | "
        f"accuracy={acc:.2%}"
    )


# ── PREDICT single ────────────────────────────────────────────────────────────
def predict(company_obj):
    """Return churn risk % (0–100) for one company."""
    features = _build_features(company_obj)

    if not os.path.exists(MODEL_PATH):
        return _rule_based_score(features)

    try:
        model  = joblib.load(MODEL_PATH)
        scaler = joblib.load(SCALER_PATH)
        f_scaled = scaler.transform(np.array([features], dtype=float))
        prob = model.predict_proba(f_scaled)[0][1]
        return round(prob * 100)
    except Exception as e:
        logger.warning(f"[Churn] predict() fallback: {e}")
        return _rule_based_score(features)


def _rule_based_score(features):
    """Fallback when model not trained yet."""
    days_inactive    = features[0]
    avg_survey       = features[2]
    open_t           = features[3]
    missed           = features[4]
    health_encoded   = features[6]
    score = (
        (days_inactive / 90) * 35
        + missed * 10
        + open_t  * 8
        + max(0, (70 - avg_survey) / 70) * 25
        + health_encoded * 10
    )
    return min(100, round(score))


# ── PREDICT BATCH ─────────────────────────────────────────────────────────────
def predict_batch(companies_queryset):
    """
    Returns list of dicts sorted by churn_risk desc.
    [{id, name, churn_risk, revenue, days_inactive,
      open_tickets, missed_followups, reason, health}, ...]
    """
    from django.db.models import Sum

    now           = timezone.now()
    model_loaded  = os.path.exists(MODEL_PATH)
    scaler_loaded = os.path.exists(SCALER_PATH)

    model, scaler = None, None
    if model_loaded and scaler_loaded:
        try:
            model  = joblib.load(MODEL_PATH)
            scaler = joblib.load(SCALER_PATH)
        except Exception as e:
            logger.warning(f"[Churn] Could not load model: {e}")
            model, scaler = None, None

    results = []
    for company in companies_queryset:
        try:
            features = _build_features(company, now)

            if model and scaler:
                f_scaled = scaler.transform(np.array([features], dtype=float))
                risk = round(model.predict_proba(f_scaled)[0][1] * 100)
            else:
                risk = _rule_based_score(features)

            try:
                revenue = float(
                    company.deals.filter(stage="won")
                    .aggregate(t=Sum("value"))["t"] or 0
                )
            except Exception:
                revenue = 0.0

            days_inactive    = features[0]
            avg_survey       = features[2]
            open_t           = features[3]
            missed           = features[4]

            if days_inactive > 60:
                reason = f"No activity in {int(days_inactive)} days"
            elif open_t >= 3:
                reason = f"{int(open_t)} unresolved support tickets"
            elif missed >= 2:
                reason = f"{int(missed)} missed follow-ups"
            elif avg_survey < 55:
                reason = f"Low satisfaction ({avg_survey:.0f}/100)"
            elif company.health in ("at-risk", "inactive"):
                reason = f"Account health: {company.health}"
            else:
                reason = "Low engagement signals"

            results.append({
                "id":               company.id,
                "name":             company.name,
                "churn_risk":       risk,
                "revenue":          revenue,
                "days_inactive":    int(days_inactive),
                "open_tickets":     int(open_t),
                "missed_followups": int(missed),
                "avg_survey":       float(avg_survey),
                "reason":           reason,
                "health":           company.health,
            })
        except Exception as e:
            logger.warning(f"[Churn] Skipping {company.id}: {e}")
            continue

    return sorted(results, key=lambda x: -x["churn_risk"])
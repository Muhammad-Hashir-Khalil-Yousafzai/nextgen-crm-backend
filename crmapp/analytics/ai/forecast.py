"""
Sales Forecast Model — Linear Regression
==========================================
Input  : Monthly won deal revenue (from crm_deals.deals)
Output : Predicted revenue for next N months + confidence bands

Algorithm:
  - X = month index (0, 1, 2, 3 ...)
  - y = total won revenue that month
  - Fit LinearRegression → predict next 3-4 months
  - Confidence bands: ±15% (low), ±25% (high)
"""

import os
import logging
from datetime import date
from dateutil.relativedelta import relativedelta

import joblib
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_percentage_error

logger = logging.getLogger(__name__)

MODEL_DIR  = os.path.join(os.path.dirname(__file__), "..", "models_dir")
MODEL_PATH = os.path.join(MODEL_DIR, "forecast_model.pkl")

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ── TRAIN ─────────────────────────────────────────────────────────────────────
def train(monthly_revenue_list):
    """
    Train on a list of monthly revenue values.
    Minimum 4 months needed.

    Parameters
    ----------
    monthly_revenue_list : list[float]
        e.g. [480000, 528000, 634000, 712000, 880000, 950000]

    Returns
    -------
    (success: bool, message: str)
    """
    if len(monthly_revenue_list) < 4:
        return False, f"Need ≥4 months of revenue data, got {len(monthly_revenue_list)}"

    X = np.array(range(len(monthly_revenue_list))).reshape(-1, 1)
    y = np.array(monthly_revenue_list, dtype=float)

    model = LinearRegression()
    model.fit(X, y)

    # MAPE on training data (only meaningful metric for small datasets)
    y_pred = model.predict(X)
    mape   = mean_absolute_percentage_error(y, y_pred)
    logger.info(f"[Forecast] MAPE on training data: {mape:.2%}")

    # Save model + metadata
    payload = {
        "model":        model,
        "n_months":     len(monthly_revenue_list),
        "last_revenue": float(monthly_revenue_list[-1]),
        "mape":         mape,
    }
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(payload, MODEL_PATH)

    return True, f"Trained on {len(monthly_revenue_list)} months | MAPE={mape:.2%}"


# ── PREDICT ───────────────────────────────────────────────────────────────────
def predict(n_months=4, history_length=None):
    """
    Predict next n_months revenue.

    Returns list of dicts:
    [{"month": "Apr '26", "forecast": 1200000, "low": 1020000, "high": 1380000}, ...]
    """
    if not os.path.exists(MODEL_PATH):
        logger.warning("[Forecast] Model not trained yet — returning linear extrapolation")
        # Fallback: simple growth assumption
        base = 900000
        results = []
        today = date.today()
        for i in range(n_months):
            future = today + relativedelta(months=i + 1)
            mid    = round(base * (1 + 0.05 * (i + 1)))
            results.append({
                "month":    f"{MONTH_NAMES[future.month - 1]} '{str(future.year)[2:]}",
                "actual":   None,
                "forecast": mid,
                "low":      round(mid * 0.85),
                "high":     round(mid * 1.15),
            })
        return results

    payload  = joblib.load(MODEL_PATH)
    model    = payload["model"]
    n_hist   = history_length or payload["n_months"]

    # Future month indices
    future_idx = np.array(range(n_hist, n_hist + n_months)).reshape(-1, 1)
    predictions = model.predict(future_idx)

    today = date.today()
    results = []
    for i, pred in enumerate(predictions):
        pred = max(float(pred), 0)                         # never negative
        future = today + relativedelta(months=i + 1)
        results.append({
            "month":    f"{MONTH_NAMES[future.month - 1]} '{str(future.year)[2:]}",
            "actual":   None,
            "forecast": round(pred),
            "low":      round(pred * 0.85),
            "high":     round(pred * 1.20),
        })

    return results


# ── HISTORY + FORECAST COMBINED (for the chart in forecaste.js) ───────────────
def history_and_forecast(monthly_qs, n_future=4):
    """
    Combines actual monthly data + future forecast into one list.

    monthly_qs: values queryset like
      Deal.objects.filter(stage='won')
          .annotate(month=TruncMonth('close_date'))
          .values('month').annotate(revenue=Sum('value')).order_by('month')

    Returns list of dicts for the chart:
    [
      {"month": "Sep '25", "actual": 548000, "forecast": None, "low": None, "high": None},
      ...
      {"month": "Apr '26", "actual": None, "forecast": 920000, "low": 782000, "high": 1104000},
    ]
    """
    history = []
    revenue_list = []

    for row in monthly_qs:
        month_date = row["month"]
        rev        = float(row["revenue"] or 0)
        label      = f"{MONTH_NAMES[month_date.month - 1]} '{str(month_date.year)[2:]}"
        history.append({
            "month":    label,
            "actual":   round(rev),
            "forecast": None,
            "low":      None,
            "high":     None,
        })
        revenue_list.append(rev)

    # Auto-retrain if model missing
    if not os.path.exists(MODEL_PATH) and len(revenue_list) >= 4:
        train(revenue_list)

    future = predict(n_months=n_future, history_length=len(revenue_list))
    return history + future
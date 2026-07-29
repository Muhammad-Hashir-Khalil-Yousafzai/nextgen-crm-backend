"""
crmapp/xai/views.py

API endpoints consumed by the Explainable AI frontend.

Endpoints (all at /api/xai/):
  GET    models/                          → list all ML models
  GET    models/{id}/                     → single model detail
  POST   models/{id}/compute_importance/  → recompute global importance

  GET    predictions/                     → list predictions (last 50)
  GET    predictions/{id}/                → full prediction + explanation
  POST   predictions/{id}/explain/        → trigger SHAP explanation
  POST   predictions/{id}/counterfactuals/ → generate DiCE counterfactuals

  GET    bias/                            → all bias audit results
  POST   bias/run_audit/                  → run a new bias audit

  GET    audit_log/                       → audit trail (last 100)

  GET    issues/                          → open model issues
  POST   issues/{id}/resolve/             → mark issue resolved

  GET    dashboard/stats/                 → KPI numbers for dashboard tab
  GET    global_importance/               → global feature importance
"""

import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from .models import (
    MLModel, Prediction, Explanation,
    BiasAudit, ModelIssue, GlobalImportance,
)
from .serializers import (
    MLModelSerializer,
    PredictionSerializer,
    PredictionListSerializer,
    AuditLogSerializer,
    BiasAuditSerializer,
    ModelIssueSerializer,
    GlobalImportanceSerializer,
)
from .services import (
    explain_prediction,
    generate_counterfactuals,
    run_bias_audit,
    compute_global_importance,
    get_dashboard_stats,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# MLModel ViewSet — /api/xai/models/
# ─────────────────────────────────────────────────────────────────────────────

class MLModelViewSet(viewsets.ReadOnlyModelViewSet):
    queryset           = MLModel.objects.filter(active=True).order_by("domain", "name")
    serializer_class   = MLModelSerializer
    permission_classes = [AllowAny]

    # POST /models/{id}/compute_importance/
    @action(detail=True, methods=["post"], url_path="compute_importance")
    def compute_importance(self, request, pk=None):
        """Recomputes global feature importance for this model."""
        ml_model = self.get_object()
        try:
            results = compute_global_importance(ml_model)
            return Response({
                "success": True,
                "message": f"Global importance recomputed for '{ml_model.name}'.",
                "features_computed": len(results),
            })
        except Exception as e:
            logger.error(f"compute_importance failed: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────────────────────
# Prediction ViewSet — /api/xai/predictions/
# ─────────────────────────────────────────────────────────────────────────────

class PredictionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset           = Prediction.objects.select_related("model").order_by("-created_at")
    permission_classes = [AllowAny]

    def get_serializer_class(self):
        if self.action == "list":
            return PredictionListSerializer
        return PredictionSerializer

    def list(self, request, *args, **kwargs):
        """Returns last 50 predictions, optionally filtered by domain."""
        qs = self.get_queryset()

        domain = request.query_params.get("domain")
        if domain:
            qs = qs.filter(model__domain=domain)

        model_id = request.query_params.get("model_id")
        if model_id:
            qs = qs.filter(model_id=model_id)

        qs = qs[:50]
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    # POST /predictions/{id}/explain/
    @action(detail=True, methods=["post"], url_path="explain")
    def explain(self, request, pk=None):
        """
        Triggers SHAP explanation for a prediction.
        If an explanation already exists, returns it (idempotent).

        Optional body:
          { "initiated_by": "Risk Engine", "explainer_type": "tree" }
        """
        prediction = self.get_object()

        # Return existing explanation if already computed
        if hasattr(prediction, "explanation"):
            serializer = PredictionSerializer(prediction)
            return Response({
                "success":    True,
                "cached":     True,
                "prediction": serializer.data,
            })

        initiated_by   = request.data.get("initiated_by", "API")
        explainer_type = request.data.get("explainer_type", "auto")

        try:
            explain_prediction(
                prediction     = prediction,
                explainer_type = explainer_type,
                initiated_by   = initiated_by,
            )
            prediction.refresh_from_db()
            serializer = PredictionSerializer(prediction)
            return Response({
                "success":    True,
                "cached":     False,
                "prediction": serializer.data,
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"explain failed for {prediction.id}: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # POST /predictions/{id}/counterfactuals/
    @action(detail=True, methods=["post"], url_path="counterfactuals")
    def counterfactuals(self, request, pk=None):
        """
        Generates DiCE counterfactuals for a prediction.
        Body: { "num_cfs": 3 }
        """
        prediction = self.get_object()
        num_cfs    = int(request.data.get("num_cfs", 3))

        try:
            results = generate_counterfactuals(prediction, num_cfs=num_cfs)
            return Response({
                "success":         True,
                "counterfactuals": len(results),
                "message":         f"Generated {len(results)} counterfactual scenarios.",
            })
        except Exception as e:
            logger.error(f"counterfactuals failed: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────────────────────
# Bias ViewSet — /api/xai/bias/
# ─────────────────────────────────────────────────────────────────────────────

class BiasViewSet(viewsets.ReadOnlyModelViewSet):
    queryset           = BiasAudit.objects.select_related("model").prefetch_related("groups").order_by("-run_at")
    serializer_class   = BiasAuditSerializer
    permission_classes = [AllowAny]

    # POST /bias/run_audit/
    @action(detail=False, methods=["post"], url_path="run_audit")
    def run_audit(self, request):
        """
        Runs a new bias audit.

        Body:
          {
            "model_id": "mdl-abc123",
            "protected_attribute": "Gender",
            "groups": [
              { "label": "Male",   "rate": 0.64, "size": 4821 },
              { "label": "Female", "rate": 0.58, "size": 3944 }
            ]
          }
        """
        model_id   = request.data.get("model_id")
        attribute  = request.data.get("protected_attribute")
        groups     = request.data.get("groups", [])

        if not all([model_id, attribute, groups]):
            return Response(
                {"error": "model_id, protected_attribute, and groups are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            ml_model = MLModel.objects.get(pk=model_id)
            audit    = run_bias_audit(ml_model, attribute, groups)
            serializer = BiasAuditSerializer(audit)
            return Response({
                "success": True,
                "audit":   serializer.data,
                "message": f"Bias audit complete. Severity: {audit.severity.upper()}",
            }, status=status.HTTP_201_CREATED)

        except MLModel.DoesNotExist:
            return Response({"error": "Model not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"run_audit failed: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────────────────────
# Audit Log ViewSet — /api/xai/audit_log/
# ─────────────────────────────────────────────────────────────────────────────

class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Returns explanation records as a flat audit trail.
    Matches the shape your Audit Trail tab expects.
    """
    queryset = (
        Explanation.objects
        .select_related("prediction", "prediction__model")
        .order_by("-created_at")[:100]
    )
    serializer_class   = AuditLogSerializer
    permission_classes = [AllowAny]

    # POST /audit_log/{id}/mark_exported/
    @action(detail=True, methods=["post"], url_path="mark_exported")
    def mark_exported(self, request, pk=None):
        expl = self.get_object()
        expl.exported = True
        expl.save(update_fields=["exported"])
        return Response({"success": True, "message": "Marked as exported."})


# ─────────────────────────────────────────────────────────────────────────────
# ModelIssue ViewSet — /api/xai/issues/
# ─────────────────────────────────────────────────────────────────────────────

class ModelIssueViewSet(viewsets.ReadOnlyModelViewSet):
    queryset           = ModelIssue.objects.select_related("model").filter(resolved=False).order_by("-detected_at")
    serializer_class   = ModelIssueSerializer
    permission_classes = [AllowAny]

    # POST /issues/{id}/resolve/
    @action(detail=True, methods=["post"], url_path="resolve")
    def resolve(self, request, pk=None):
        issue = self.get_object()
        issue.resolved    = True
        issue.resolved_at = __import__("django.utils.timezone", fromlist=["now"]).now()
        issue.save(update_fields=["resolved", "resolved_at"])
        return Response({"success": True, "message": f"Issue '{issue.issue_type}' marked resolved."})


# ─────────────────────────────────────────────────────────────────────────────
# Global Importance ViewSet — /api/xai/global_importance/
# ─────────────────────────────────────────────────────────────────────────────

class GlobalImportanceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset           = GlobalImportance.objects.select_related("model").order_by("-avg_importance")
    serializer_class   = GlobalImportanceSerializer
    permission_classes = [AllowAny]


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard ViewSet — /api/xai/dashboard/
# ─────────────────────────────────────────────────────────────────────────────

class DashboardViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    # GET /dashboard/stats/
    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        """Returns aggregated KPI numbers for the Dashboard tab."""
        return Response(get_dashboard_stats())

"""
crmapp/xai/serializers.py
"""

from rest_framework import serializers
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


class FeatureContributionSerializer(serializers.ModelSerializer):
    class Meta:
        model  = FeatureContribution
        fields = [
            "id", "feature_name", "feature_value",
            "shap_contribution", "direction", "importance_score", "rank",
        ]


class CounterfactualSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Counterfactual
        fields = [
            "id", "scenario_index", "change_description",
            "impact_label", "probability",
        ]


class ExplanationSerializer(serializers.ModelSerializer):
    feature_contributions = FeatureContributionSerializer(many=True, read_only=True)

    class Meta:
        model  = Explanation
        fields = [
            "id", "explainer_used", "nl_explanation",
            "base_value", "initiated_by", "exported", "created_at",
            "feature_contributions",
        ]


class PredictionSerializer(serializers.ModelSerializer):
    """
    Full prediction + explanation + counterfactuals — used by Explanations tab.
    """
    model_name   = serializers.CharField(source="model.name",   read_only=True)
    model_domain = serializers.CharField(source="model.domain", read_only=True)
    model_type   = serializers.CharField(source="model.model_type", read_only=True)
    explanation  = ExplanationSerializer(read_only=True)
    counterfactuals = CounterfactualSerializer(many=True, read_only=True)

    class Meta:
        model  = Prediction
        fields = [
            "id", "subject_id", "subject_name", "subject_type",
            "prediction_label", "outcome_type",
            "confidence_score", "uncertainty_score",
            "created_at",
            "model_name", "model_domain", "model_type",
            "explanation", "counterfactuals",
        ]


class PredictionListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for the left-hand prediction list panel.
    """
    model_name   = serializers.CharField(source="model.name",   read_only=True)
    model_domain = serializers.CharField(source="model.domain", read_only=True)

    class Meta:
        model  = Prediction
        fields = [
            "id", "subject_id", "subject_name",
            "prediction_label", "outcome_type",
            "confidence_score", "created_at",
            "model_name", "model_domain",
        ]


class MLModelSerializer(serializers.ModelSerializer):
    total_predictions = serializers.IntegerField(read_only=True)
    open_issues       = serializers.IntegerField(read_only=True)

    class Meta:
        model  = MLModel
        fields = [
            "id", "name", "model_type", "domain",
            "description", "accuracy", "active",
            "total_predictions", "open_issues",
            "created_at", "updated_at",
        ]


class BiasAuditGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model  = BiasAuditGroup
        fields = ["id", "group_label", "rate_value", "sample_size", "is_flagged"]


class BiasAuditSerializer(serializers.ModelSerializer):
    groups     = BiasAuditGroupSerializer(many=True, read_only=True)
    model_name = serializers.CharField(source="model.name", read_only=True)

    class Meta:
        model  = BiasAudit
        fields = [
            "id", "model_name", "protected_attribute",
            "disparity_score", "severity", "mitigation_text",
            "run_at", "groups",
        ]


class ModelIssueSerializer(serializers.ModelSerializer):
    model_name   = serializers.CharField(source="model.name",   read_only=True)
    model_domain = serializers.CharField(source="model.domain", read_only=True)

    class Meta:
        model  = ModelIssue
        fields = [
            "id", "model_name", "model_domain",
            "issue_type", "severity", "description",
            "recommendation", "shap_drift", "affected_count",
            "resolved", "detected_at", "resolved_at",
        ]


class GlobalImportanceSerializer(serializers.ModelSerializer):
    model_name   = serializers.CharField(source="model.name",   read_only=True)
    model_domain = serializers.CharField(source="model.domain", read_only=True)

    class Meta:
        model  = GlobalImportance
        fields = [
            "id", "model_name", "model_domain",
            "feature_name", "avg_importance", "sample_count", "computed_at",
        ]


class AuditLogSerializer(serializers.ModelSerializer):
    """
    Flattened view for the Audit Trail tab — mirrors your frontend's AUDIT_LOG shape.
    """
    model_name     = serializers.CharField(source="prediction.model.name",    read_only=True)
    model_domain   = serializers.CharField(source="prediction.model.domain",  read_only=True)
    subject_id     = serializers.CharField(source="prediction.subject_id",    read_only=True)
    prediction_label = serializers.CharField(source="prediction.prediction_label", read_only=True)
    confidence_score = serializers.FloatField(source="prediction.confidence_score", read_only=True)
    outcome_type   = serializers.CharField(source="prediction.outcome_type",  read_only=True)

    class Meta:
        model  = Explanation
        fields = [
            "id", "model_name", "model_domain",
            "subject_id", "prediction_label",
            "confidence_score", "outcome_type",
            "explainer_used", "initiated_by",
            "exported", "created_at",
        ]

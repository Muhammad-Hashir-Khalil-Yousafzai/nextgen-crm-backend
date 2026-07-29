from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Deal
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Deal)
def auto_predict_deal(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        from crmapp.ai.xai.services import predict_and_explain_deal, generate_counterfactuals
        pred, expl = predict_and_explain_deal(instance, initiated_by="Auto")
        if pred.outcome_type == "negative":
            generate_counterfactuals(pred, num_cfs=3)
        logger.info(f"[XAI] Auto-prediction created for deal: {instance.title}")
    except Exception as e:
        logger.warning(f"[XAI] Auto-predict failed for deal {instance.id}: {e}")@receiver(post_save, sender=Deal)
def auto_predict_deal(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        from crmapp.ai.xai.services import predict_and_explain_deal, generate_counterfactuals, compute_global_importance
        from crmapp.ai.xai.models import MLModel
        pred, expl = predict_and_explain_deal(instance, initiated_by="Auto")
        if pred.outcome_type == "negative":
            generate_counterfactuals(pred, num_cfs=3)
        # Recompute global importance after each new prediction
        ml_model = MLModel.objects.get(name="Deal Win Predictor")
        compute_global_importance(ml_model)
        logger.info(f"[XAI] Auto-prediction created for deal: {instance.title}")
    except Exception as e:
        logger.warning(f"[XAI] Auto-predict failed for deal {instance.id}: {e}")
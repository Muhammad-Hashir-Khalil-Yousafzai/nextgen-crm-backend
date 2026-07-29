from django.db import models
from django.contrib.auth.models import User
import datetime


class Survey(models.Model):

    STATUS_CHOICES = [
        ('draft',  'Draft'),
        ('active', 'Active'),
        ('closed', 'Closed'),
    ]

    TRIGGER_CHOICES = [
        ('manual',              'Manual / Bulk Send'),
        ('ticket_closed',       'After Ticket Closure'),
        ('purchase_completed',  'After Purchase'),
        ('onboarding_complete', 'After Onboarding'),
        ('demo_completed',      'After Demo'),
    ]

    # ── Core ──────────────────────────────────────────────────────
    name        = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    status      = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    is_template = models.BooleanField(default=False)

    # ── Behaviour ─────────────────────────────────────────────────
    trigger_event       = models.CharField(max_length=30, choices=TRIGGER_CHOICES, default='manual')
    distribution_method = models.JSONField(default=list, blank=True)  # ['email','sms','link']

    # ── Questions (stored as JSON array) ──────────────────────────
    # Each item: {id, type, questionText, required, ratingScale, options, order}
    # type choices: 'rating' | 'nps' | 'text' | 'multiple_choice' | 'yes_no'
    questions = models.JSONField(default=list, blank=True)

    # ── Aggregate stats (denormalised, updated on each new response) ─
    total_sent  = models.IntegerField(default=0)
    total_responses = models.IntegerField(default=0)
    avg_rating  = models.FloatField(null=True, blank=True)
    nps         = models.IntegerField(null=True, blank=True)

    # ── Meta ──────────────────────────────────────────────────────
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='surveys_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'surveys'
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def response_rate(self):
        if not self.total_sent:
            return 0
        return round((self.total_responses / self.total_sent) * 100, 1)

    def recalculate_stats(self):
        """Call after saving a new SurveyResponse to keep denormalised fields fresh."""
        responses = self.responses.all()
        count = responses.count()
        self.total_responses = count

        if count:
            ratings = [r.csat_score for r in responses if r.csat_score is not None]
            self.avg_rating = round(sum(ratings) / len(ratings) / 20, 2) if ratings else None

            nps_scores = [r.nps_score for r in responses if r.nps_score is not None]
            if nps_scores:
                promoters  = sum(1 for s in nps_scores if s >= 9)
                detractors = sum(1 for s in nps_scores if s <= 6)
                self.nps   = round(((promoters - detractors) / len(nps_scores)) * 100)
        self.save(update_fields=['total_responses', 'avg_rating', 'nps', 'updated_at'])


class SurveyResponse(models.Model):

    SENTIMENT_CHOICES = [
        ('positive', 'Positive'),
        ('neutral',  'Neutral'),
        ('negative', 'Negative'),
    ]

    # ── Relations ─────────────────────────────────────────────────
    survey = models.ForeignKey(
        Survey, on_delete=models.CASCADE,
        related_name='responses'
    )
    contact = models.ForeignKey(
        'crm_contacts.Contact',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='survey_responses'
    )
    ticket = models.ForeignKey(
        'crm_tickets.Ticket',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='survey_responses'
    )

    # ── Customer info (denormalised) ───────────────────────────────
    customer_name   = models.CharField(max_length=255, blank=True)
    customer_avatar = models.URLField(blank=True)
    customer_email  = models.EmailField(blank=True)

    # ── Scores ────────────────────────────────────────────────────
    csat_score      = models.IntegerField(null=True, blank=True)   # 0–100
    nps_score       = models.IntegerField(null=True, blank=True)   # 0–10
    sentiment_score = models.FloatField(null=True, blank=True)     # -1.0 to 1.0

    # ── Content ───────────────────────────────────────────────────
    # answers: [{q: 'Question label', a: 'Answer text'}, ...]
    answers = models.JSONField(default=list, blank=True)
    tags    = models.JSONField(default=list, blank=True)

    # ── Meta ──────────────────────────────────────────────────────
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'survey_responses'
        ordering = ['-submitted_at']

    def __str__(self):
        return f"Response to '{self.survey.name}' by {self.customer_name or 'anonymous'}"

    def save(self, *args, **kwargs):
        # Denormalise contact fields
        if self.contact:
            if not self.customer_name:
                self.customer_name  = self.contact.name
            if not self.customer_email:
                self.customer_email = self.contact.email
            if not self.customer_avatar:
                self.customer_avatar = self.contact.avatar
        super().save(*args, **kwargs)
        # Keep survey aggregate stats up to date
        self.survey.recalculate_stats()

    @property
    def sentiment_label(self):
        if self.sentiment_score is None:
            return None
        if self.sentiment_score > 0.3:  return 'positive'
        if self.sentiment_score < -0.3: return 'negative'
        return 'neutral'

    @property
    def nps_category(self):
        if self.nps_score is None:
            return None
        if self.nps_score >= 9: return 'promoter'
        if self.nps_score >= 7: return 'passive'
        return 'detractor'
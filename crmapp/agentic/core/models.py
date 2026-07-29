import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


def make_res_id():
    return f"res-{uuid.uuid4().hex[:6]}"


class Resource(models.Model):
    STATUS_CHOICES = [
        ('active',  'Active'),
        ('busy',    'Busy'),
        ('idle',    'Idle'),
        ('offline', 'Offline'),
    ]
    TYPE_CHOICES = [
        ('AI Agent', 'AI Agent'),
        ('System',   'System'),
        ('Human',    'Human'),
    ]

    id              = models.CharField(max_length=50, primary_key=True, default=make_res_id)
    name            = models.CharField(max_length=100, unique=True)
    type            = models.CharField(max_length=20, choices=TYPE_CHOICES)
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default='idle')
    load_percentage = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    capacity        = models.IntegerField(default=100)
    current_load    = models.IntegerField(default=0) 
    color           = models.CharField(max_length=7, default='#3a9aab')
    metadata        = models.JSONField(default=dict, blank=True)
    last_heartbeat  = models.DateTimeField(auto_now=True)

    # ── NEW fields for CrewAI agent identity ──
    role            = models.TextField(blank=True, default='')
    goal            = models.TextField(blank=True, default='')
    backstory       = models.TextField(blank=True, default='')
    tools           = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = 'resources'   # ← same table name, no data loss

    def __str__(self):
        return f"{self.name} ({self.type}) - {self.status}"
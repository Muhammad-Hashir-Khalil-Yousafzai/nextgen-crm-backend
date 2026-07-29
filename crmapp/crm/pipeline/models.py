from django.db import models
from django.contrib.auth.models import User


class Pipeline(models.Model):

    STAGE_CHOICES = [
        ('Won',              'Won'),
        ('In Pipeline',      'In Pipeline'),
        ('Conversation',     'Conversation'),
        ('Follow Up',        'Follow Up'),
        ('Schedule Service', 'Schedule Service'),
        ('Lost',             'Lost'),
    ]
    STATUS_CHOICES = [
        ('Active',   'Active'),
        ('Inactive', 'Inactive'),
    ]

    name        = models.CharField(max_length=255)
    total_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    no_of_deals = models.IntegerField(default=0)
    stage       = models.CharField(max_length=50, choices=STAGE_CHOICES, default='In Pipeline')
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')
    color       = models.CharField(max_length=20, blank=True, default='#296571')
    description = models.TextField(blank=True)
    created_by  = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='pipelines_created'
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'pipelines'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} — {self.stage}"

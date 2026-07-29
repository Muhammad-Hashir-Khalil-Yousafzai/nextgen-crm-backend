from django.db import models
from django.contrib.auth.models import User


class Company(models.Model):
    TYPE_CHOICES = [
        ('client',   'Client'),
        ('vendor',   'Vendor'),
        ('partner',  'Partner'),
        ('prospect', 'Prospect'),
    ]
    HEALTH_CHOICES = [
        ('healthy',  'Healthy'),
        ('at-risk',  'At Risk'),
        ('new',      'New'),
        ('inactive', 'Inactive'),
    ]

    name               = models.CharField(max_length=255)
    code               = models.CharField(max_length=10, blank=True)
    industry           = models.CharField(max_length=100, blank=True)
    type               = models.CharField(max_length=20, choices=TYPE_CHOICES, default='prospect')
    health             = models.CharField(max_length=20, choices=HEALTH_CHOICES, default='new')
    website            = models.URLField(blank=True)
    email              = models.EmailField(blank=True)
    phone              = models.CharField(max_length=50, blank=True)
    headquarters       = models.CharField(max_length=255, blank=True)
    branches           = models.JSONField(default=list, blank=True)
    number_of_employees= models.IntegerField(default=0)
    annual_revenue     = models.BigIntegerField(default=0)
    total_revenue      = models.BigIntegerField(default=0)
    account_owner      = models.CharField(max_length=255, blank=True)
    account_owner_avatar = models.URLField(blank=True)
    social_links       = models.JSONField(default=dict, blank=True)
    tags               = models.JSONField(default=list, blank=True)
    notes              = models.TextField(blank=True)
    rating             = models.IntegerField(default=3)
    last_contact       = models.DateField(null=True, blank=True)
    created_by         = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at         = models.DateTimeField(auto_now_add=True)
    updated_at         = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'companies'
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.code and self.name:
            self.code = self.name[:2].upper()
        super().save(*args, **kwargs)

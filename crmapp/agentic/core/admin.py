from django.contrib import admin
from .models import Resource


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display    = ["name", "type", "status", "load_percentage", "last_heartbeat"]
    list_filter     = ["type", "status"]
    search_fields   = ["name", "role"]
    readonly_fields = ["id", "last_heartbeat"]
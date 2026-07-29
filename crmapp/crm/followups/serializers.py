from rest_framework import serializers
from .models import FollowUp


class FollowUpSerializer(serializers.ModelSerializer):
    """
    Full serializer — create / retrieve / update.

    Recurring
    ─────────
    On READ  : `recurring` is a computed nested object { enabled, frequency, interval }
               matching exactly the shape the frontend card/modal expects.
    On WRITE : Client may send either the flat fields (recurring_enabled,
               recurring_frequency, recurring_interval) OR a nested `recurring`
               dict — both are accepted via validate().

    Contact / Deal denormalized names
    ──────────────────────────────────
    `contact_name`, `contact_avatar`, `deal_title` are read-only computed
    fields so the frontend can render cards without extra lookups.
    """

    # ── Computed read-only ────────────────────────────────────────────────────
    recurring      = serializers.ReadOnlyField()   # property on model
    contact_name   = serializers.ReadOnlyField()
    contact_avatar = serializers.ReadOnlyField()
    deal_title     = serializers.ReadOnlyField()

    class Meta:
        model  = FollowUp
        fields = '__all__'
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'created_by',
            'recurring', 'contact_name', 'contact_avatar', 'deal_title',
        ]

    def validate(self, attrs):
        """
        Allow clients to send a nested `recurring` dict and unpack it into
        the flat DB columns.  This means both of these payloads work:

        Flat (preferred for forms):
          { "recurring_enabled": true, "recurring_frequency": "weekly", ... }

        Nested (matches frontend shape):
          { "recurring": { "enabled": true, "frequency": "weekly", "interval": 1 } }
        """
        nested = self.initial_data.get('recurring')
        if isinstance(nested, dict):
            attrs.setdefault('recurring_enabled',   nested.get('enabled',   False))
            attrs.setdefault('recurring_frequency',  nested.get('frequency', 'weekly'))
            attrs.setdefault('recurring_interval',   nested.get('interval',  1))
        return attrs


class FollowUpListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for list views — only the fields the
    card/table UI needs (mirrors LeadListSerializer / DealListSerializer).
    """

    recurring      = serializers.ReadOnlyField()
    contact_name   = serializers.ReadOnlyField()
    contact_avatar = serializers.ReadOnlyField()
    deal_title     = serializers.ReadOnlyField()

    class Meta:
        model  = FollowUp
        fields = [
            'id',
            'title',
            'description',
            'type',
            'priority',
            'status',
            'due_date',
            'reminder_time',
            'assigned_to',
            'tags',
            'notes',
            # Recurring (nested, read-only)
            'recurring',
            'recurring_enabled',
            'recurring_frequency',
            'recurring_interval',
            # FK IDs
            'contact',
            'deal',
            'activity',
            # Denormalized display fields
            'contact_name',
            'contact_avatar',
            'deal_title',
            'created_at',
        ]
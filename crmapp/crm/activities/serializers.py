from rest_framework import serializers
from .models import Activity


class ActivitySerializer(serializers.ModelSerializer):
    """
    Full serializer — used for create / retrieve / update.
    Includes owner_image (Base64) and computed helpers.
    """
    is_overdue  = serializers.ReadOnlyField()
    has_image   = serializers.ReadOnlyField()

    # Friendly display names for related objects
    contact_name = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    lead_name    = serializers.SerializerMethodField()
    deal_title   = serializers.SerializerMethodField()

    class Meta:
        model  = Activity
        fields = '__all__'
        read_only_fields = [
            'id', 'created_date', 'updated_at', 'created_by',
            'is_overdue', 'has_image',
            'contact_name', 'company_name', 'lead_name', 'deal_title',
        ]

    def get_contact_name(self, obj):
        return obj.contact.name if obj.contact else None

    def get_company_name(self, obj):
        return obj.company.name if obj.company else None

    def get_lead_name(self, obj):
        return obj.lead.name if obj.lead else None

    def get_deal_title(self, obj):
        return obj.deal.title if obj.deal else None

    # ── owner_image validation ─────────────────────────────────────
    def validate_owner_image(self, value):
        """
        Accepts:
          • Empty string / None → owner icon will be shown by frontend
          • A valid Base64 data URI: data:<mime>;base64,<payload>
          • Raw Base64 string (no data-URI prefix)
        Rejects payloads that are clearly not Base64.
        """
        if not value:
            return value

        import base64, re

        # Strip data-URI prefix if present
        data_uri_re = re.compile(
            r'^data:(image/(?:png|jpeg|jpg|gif|webp|svg\+xml));base64,(.+)$',
            re.IGNORECASE
        )
        m = data_uri_re.match(value)
        if m:
            raw = m.group(2)
        else:
            raw = value  # treat as raw Base64

        # Validate the Base64 payload
        try:
            base64.b64decode(raw, validate=True)
        except Exception:
            raise serializers.ValidationError(
                "owner_image must be a valid Base64 string or data URI "
                "(data:image/<type>;base64,<payload>)."
            )

        return value


class ActivityListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for the list view / table.
    Omits owner_image to keep list responses small;
    has_image lets the frontend decide whether to fetch
    the full record or show the icon.
    """
    is_overdue = serializers.ReadOnlyField()
    has_image  = serializers.ReadOnlyField()

    class Meta:
        model  = Activity
        fields = [
            'id', 'title', 'activity_type', 'due_date', 'created_date',
            'owner', 'has_image', 'is_overdue',
            'contact', 'company', 'lead', 'deal',
            'notes', 'updated_at',
        ]

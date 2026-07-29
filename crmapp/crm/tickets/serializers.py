from rest_framework import serializers
from .models import Ticket, TicketReply
from django.contrib.auth.models import User

class TicketReplySerializer(serializers.ModelSerializer):
    class Meta:
        model  = TicketReply
        fields = '__all__'
        read_only_fields = ['created_at']


class TicketSerializer(serializers.ModelSerializer):
    replies         = TicketReplySerializer(many=True, read_only=True)
    sla_status      = serializers.ReadOnlyField()
    sla_elapsed_pct = serializers.ReadOnlyField()
    is_unresponded  = serializers.ReadOnlyField()

    contact = serializers.PrimaryKeyRelatedField(
        queryset=Ticket._meta.get_field('contact').related_model.objects.all(),
        allow_null=True,
        required=False,
    )

    customer_avatar = serializers.CharField(required=False, allow_blank=True)

    assigned_to = serializers.PrimaryKeyRelatedField(
    queryset=User.objects.all(),
    allow_null=True,
    required=False,
    )

    created_by = serializers.PrimaryKeyRelatedField(
    queryset=User.objects.all(),
    allow_null=True,
    required=False,
    )

    

    class Meta:
        model  = Ticket
        fields = '__all__'
        read_only_fields = ['ticket_number', 'created_at', 'updated_at']
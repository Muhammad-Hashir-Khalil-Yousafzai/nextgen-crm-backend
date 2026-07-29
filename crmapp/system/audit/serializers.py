# audit/serializers.py
"""
The serializer is kept for direct AuditLog model usage (e.g. admin).
The audit LIST endpoint now returns plain dicts from services.get_audit_logs()
so it doesn't go through this serializer — no change needed there.
"""
from rest_framework import serializers
from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    user_name     = serializers.SerializerMethodField()
    user_initials = serializers.SerializerMethodField()
    user_role     = serializers.CharField(source='role_at_time', read_only=True)

    class Meta:
        model  = AuditLog
        fields = [
            'id', 'user', 'user_name', 'user_initials', 'user_role',
            'user_snapshot', 'action', 'module', 'entity',
            'ip_address', 'city', 'device_info',
            'before_data', 'after_data', 'severity', 'timestamp',
        ]
        read_only_fields = ['id', 'timestamp']

    def get_user_name(self, obj):
        if obj.user_snapshot and obj.user_snapshot.get('name'):
            return obj.user_snapshot['name']
        if obj.user:
            p = getattr(obj.user, 'profile', None)
            return p.full_name if p else obj.user.email
        return 'System'

    def get_user_initials(self, obj):
        if obj.user_snapshot and obj.user_snapshot.get('initials'):
            return obj.user_snapshot['initials']
        if obj.user:
            p = getattr(obj.user, 'profile', None)
            return p.avatar_initials if p else ''
        return 'SY'
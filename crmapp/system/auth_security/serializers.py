# auth_security/serializers.py
from rest_framework import serializers
from .models import LoginLog, MFAUser, APIToken, SSOProvider, SecurityPolicy, BlockedIP


# ──────────────────────────────────────────────
# LOGIN LOG
# ──────────────────────────────────────────────

class LoginLogSerializer(serializers.ModelSerializer):
    user_name     = serializers.SerializerMethodField()
    user_initials = serializers.SerializerMethodField()

    class Meta:
        model  = LoginLog
        fields = [
            'id', 'user', 'user_name', 'user_initials',
            'email_attempted', 'status',
            'ip_address', 'city', 'device_info',
            'mfa_used', 'session_duration', 'timestamp',
        ]
        read_only_fields = ['id', 'timestamp']

    def get_user_name(self, obj) -> str:
        if not obj.user:
            return 'Unknown'
        profile = getattr(obj.user, 'profile', None)
        return profile.full_name if profile else obj.user.email

    def get_user_initials(self, obj) -> str:
        if not obj.user:
            return '??'
        profile = getattr(obj.user, 'profile', None)
        return profile.avatar_initials if profile else ''


# ──────────────────────────────────────────────
# MFA USER
# ──────────────────────────────────────────────

class MFAUserSerializer(serializers.ModelSerializer):
    user_name              = serializers.SerializerMethodField()
    user_email             = serializers.CharField(source='user.email', read_only=True)
    user_initials          = serializers.SerializerMethodField()
    user_role              = serializers.SerializerMethodField()
    backup_codes_remaining = serializers.IntegerField(read_only=True)

    class Meta:
        model  = MFAUser
        fields = [
            'id', 'user', 'user_name', 'user_email', 'user_initials',
            'user_role', 'mfa_enabled', 'method',
            'backup_codes_remaining', 'last_verified',
        ]
        read_only_fields = ['id', 'backup_codes_remaining', 'last_verified']

    def get_user_name(self, obj) -> str:
        profile = getattr(obj.user, 'profile', None)
        return profile.full_name if profile else obj.user.email

    def get_user_initials(self, obj) -> str:
        profile = getattr(obj.user, 'profile', None)
        return profile.avatar_initials if profile else ''

    def get_user_role(self, obj) -> str | None:
        ur = (
            obj.user.user_roles
            .filter(is_active=True)
            .select_related('role')
            .first()
        )
        return ur.role.name if ur else None


# ──────────────────────────────────────────────
# API TOKEN
# ──────────────────────────────────────────────

class APITokenSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model  = APIToken
        fields = [
            'id', 'name', 'token_prefix', 'scopes',
            'created_by', 'created_by_name', 'status',
            'call_count', 'created_at', 'expires_at', 'last_used_at',
        ]
        read_only_fields = [
            'id', 'token_prefix', 'call_count',
            'created_at', 'last_used_at',
        ]
        # NOTE: `token` (hashed value) is intentionally excluded.
        # The raw token is injected once in the view's create() response.

    def get_created_by_name(self, obj) -> str | None:
        if not obj.created_by:
            return None
        profile = getattr(obj.created_by, 'profile', None)
        return profile.full_name if profile else obj.created_by.email


# ──────────────────────────────────────────────
# SSO PROVIDER
# ──────────────────────────────────────────────

class SSOProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SSOProvider
        fields = [
            'id', 'name', 'icon_label', 'color_hex', 'protocol',
            'client_id', 'metadata_url', 'redirect_uri',
            'tenant_domain', 'is_enabled', 'user_count',
        ]
        read_only_fields = ['id', 'user_count']
        # `client_secret` intentionally excluded — write-only / never exposed in API.

    def validate_color_hex(self, value: str) -> str:
        """Ensure colour is a valid 6-digit hex string, e.g. #1A2B3C."""
        import re
        if not re.fullmatch(r'#[0-9A-Fa-f]{6}', value):
            raise serializers.ValidationError(
                'color_hex must be a 6-digit hex colour, e.g. #1A2B3C'
            )
        return value.upper()


# ──────────────────────────────────────────────
# SECURITY POLICY  (singleton)
# ──────────────────────────────────────────────

class SecurityPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model  = SecurityPolicy
        fields = [
            'id',
            # Brute-force / lockout
            'max_attempts', 'lockout_duration',
            # Session
            'session_timeout', 'max_sessions',
            # Auth features
            'captcha_enabled', 'ip_restriction',
            'passwordless_enabled', 'adaptive_auth',
            'require_mfa',
            # Remember-me
            'remember_me', 'remember_me_days',
            # Token lifetimes (minutes)
            'access_token_expiry', 'refresh_token_expiry',
            'updated_at',
        ]
        read_only_fields = ['id', 'updated_at']

    def validate_max_attempts(self, value: int) -> int:
        if value < 1:
            raise serializers.ValidationError('max_attempts must be at least 1.')
        return value

    def validate_session_timeout(self, value: int) -> int:
        if value < 5:
            raise serializers.ValidationError(
                'session_timeout must be at least 5 minutes.'
            )
        return value

    def validate_remember_me_days(self, value: int) -> int:
        if value < 1 or value > 365:
            raise serializers.ValidationError(
                'remember_me_days must be between 1 and 365.'
            )
        return value


# ──────────────────────────────────────────────
# BLOCKED IP
# ──────────────────────────────────────────────

class BlockedIPSerializer(serializers.ModelSerializer):
    blocked_by_name = serializers.SerializerMethodField()

    class Meta:
        model  = BlockedIP
        fields = [
            'id', 'ip_address', 'reason', 'city',
            'blocked_by', 'blocked_by_name',
            'blocked_at', 'is_active',
        ]
        read_only_fields = ['id', 'blocked_at', 'blocked_by']

    def get_blocked_by_name(self, obj) -> str | None:
        if not obj.blocked_by:
            return None
        profile = getattr(obj.blocked_by, 'profile', None)
        return profile.full_name if profile else obj.blocked_by.email

    def validate_ip_address(self, value: str) -> str:
        """Accept both IPv4 and IPv6; reject obviously invalid strings."""
        import ipaddress
        try:
            ipaddress.ip_address(value)
        except ValueError:
            raise serializers.ValidationError(
                f'"{value}" is not a valid IP address.'
            )
        return value
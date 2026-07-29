# usermanage/serializers.py
from rest_framework import serializers
from django.contrib.auth.models import User as AuthUser
from django.contrib.auth.password_validation import validate_password

from crmapp.system.roles.models import Role
from .models import UserProfile, Department, UserSession, UserActivityLog


# ──────────────────────────────────────────────
# DEPARTMENT
# ──────────────────────────────────────────────
class DepartmentSerializer(serializers.ModelSerializer):
    head_name  = serializers.SerializerMethodField()
    user_count = serializers.SerializerMethodField()

    class Meta:
        model  = Department
        fields = ['id', 'slug', 'name', 'color_hex', 'head', 'head_name', 'size', 'user_count']
        read_only_fields = ['id', 'size', 'user_count']

    def get_head_name(self, obj):
        if obj.head:
            p = getattr(obj.head, 'profile', None)
            return p.full_name if p else obj.head.get_full_name()
        return None

    def get_user_count(self, obj):
        return obj.users.filter(status='active').count()


# ──────────────────────────────────────────────
# USER PROFILE — LIST (table/grid)
# ──────────────────────────────────────────────
class UserListSerializer(serializers.ModelSerializer):
    """
    Matches frontend USERS_INIT exactly.
    Reads from UserProfile but exposes email/date_joined/last_login from auth_user.
    """
    email        = serializers.EmailField(source='user.email',        read_only=True)
    date_joined = serializers.DateTimeField(source='user.date_joined', read_only=True)
    last_login   = serializers.DateTimeField(source='user.last_login', read_only=True, allow_null=True)
    is_active    = serializers.BooleanField(source='user.is_active',  read_only=True)
    department   = DepartmentSerializer(read_only=True)
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        source='department',
        write_only=True,
        required=False,
        allow_null=True,
    )
    role_display  = serializers.SerializerMethodField()
    mfa_enabled   = serializers.SerializerMethodField()

    class Meta:
        model  = UserProfile
        fields = [
            'id', 'email', 'full_name', 'phone',
            'avatar_initials', 'city', 'status',
            'department', 'department_id',
            'role_display', 'mfa_enabled',
            'login_count', 'action_count',
            'date_joined', 'last_login', 'is_active',
        ]
        read_only_fields = [
            'id', 'avatar_initials', 'login_count',
            'action_count', 'date_joined', 'last_login', 'is_active',
        ]

    def get_role_display(self, obj):
        ur = obj.user.user_roles.filter(is_active=True).select_related('role').first()
        return ur.role.name if ur else None

    def get_mfa_enabled(self, obj):
        mfa = getattr(obj.user, 'mfa', None)
        return mfa.mfa_enabled if mfa else False


# ──────────────────────────────────────────────
# USER PROFILE — DETAIL (profile viewer)
# ──────────────────────────────────────────────
class UserDetailSerializer(serializers.ModelSerializer):
    email          = serializers.EmailField(source='user.email',        read_only=True)
    date_joined = serializers.DateTimeField(source='user.date_joined', read_only=True)
    last_login     = serializers.DateTimeField(source='user.last_login', read_only=True, allow_null=True)
    is_active      = serializers.BooleanField(source='user.is_active',  read_only=True)
    department     = DepartmentSerializer(read_only=True)
    department_id  = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        source='department',
        write_only=True,
        required=False, allow_null=True,
    )
    role_display   = serializers.SerializerMethodField()
    mfa_enabled    = serializers.SerializerMethodField()
    active_sessions = serializers.SerializerMethodField()

    class Meta:
        model  = UserProfile
        fields = [
            'id', 'email', 'full_name', 'phone',
            'avatar_initials', 'city', 'status',
            'department', 'department_id',
            'role_display', 'mfa_enabled',
            'login_count', 'action_count',
            'date_joined', 'last_login', 'is_active',
            'active_sessions',
        ]
        read_only_fields = [
            'id', 'avatar_initials', 'login_count',
            'action_count', 'date_joined', 'last_login', 'is_active',
        ]

    def get_role_display(self, obj):
        ur = obj.user.user_roles.filter(is_active=True).select_related('role').first()
        return ur.role.name if ur else None

    def get_mfa_enabled(self, obj):
        mfa = getattr(obj.user, 'mfa', None)
        return mfa.mfa_enabled if mfa else False

    def get_active_sessions(self, obj):
        sessions = obj.user.sessions.filter(is_active=True).order_by('-last_activity')[:5]
        return UserSessionSerializer(sessions, many=True).data


# ──────────────────────────────────────────────
# CREATE USER
# ──────────────────────────────────────────────
class UserCreateSerializer(serializers.Serializer):
    full_name     = serializers.CharField(max_length=100)
    email         = serializers.EmailField()
    password      = serializers.CharField(write_only=True, validators=[validate_password])
    phone         = serializers.CharField(max_length=25, required=False, allow_blank=True)
    city          = serializers.CharField(max_length=60, required=False, allow_blank=True)
    status        = serializers.ChoiceField(choices=UserProfile.STATUS_CHOICES, default='active')
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        required=False, allow_null=True
    )
    role_id = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(),
        required=False, allow_null=True
    )

    def validate_email(self, value):
        if AuthUser.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value.lower().strip()

    def create(self, validated_data):
        # This is called by .save() — delegate to services
        from . import services
        request = self.context.get('request')
        actor   = request.user if request else None
        return services.create_user(validated_data, actor=actor)

    def update(self, instance, validated_data):
        raise NotImplementedError
# ──────────────────────────────────────────────
# STATUS UPDATE
# ──────────────────────────────────────────────
class UserStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=UserProfile.STATUS_CHOICES)


# ──────────────────────────────────────────────
# PASSWORD RESET
# ──────────────────────────────────────────────
class UserPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True, validators=[validate_password])


# ──────────────────────────────────────────────
# SESSION
# ──────────────────────────────────────────────
class UserSessionSerializer(serializers.ModelSerializer):
    user_name     = serializers.SerializerMethodField()
    user_initials = serializers.SerializerMethodField()

    class Meta:
        model  = UserSession
        fields = [
            'id', 'user', 'user_name', 'user_initials',
            'ip_address', 'city', 'device_info',
            'session_key', 'is_active',
            'created_at', 'last_activity', 'expires_at',
        ]
        read_only_fields = ['id', 'created_at', 'last_activity']

    def get_user_name(self, obj):
        p = getattr(obj.user, 'profile', None)
        return p.full_name if p else obj.user.email

    def get_user_initials(self, obj):
        p = getattr(obj.user, 'profile', None)
        return p.avatar_initials if p else ''


# ──────────────────────────────────────────────
# ACTIVITY LOG
# ──────────────────────────────────────────────
class UserActivityLogSerializer(serializers.ModelSerializer):
    actor_name       = serializers.SerializerMethodField()
    actor_initials   = serializers.SerializerMethodField()
    target_user_name = serializers.SerializerMethodField()

    class Meta:
        model  = UserActivityLog
        fields = [
            'id', 'actor', 'actor_name', 'actor_initials',
            'target_user', 'target_user_name',
            'action', 'description', 'timestamp',
        ]
        read_only_fields = ['id', 'timestamp']

    def get_actor_name(self, obj):
        if not obj.actor: return 'System'
        p = getattr(obj.actor, 'profile', None)
        return p.full_name if p else obj.actor.email

    def get_actor_initials(self, obj):
        if not obj.actor: return 'SY'
        p = getattr(obj.actor, 'profile', None)
        return p.avatar_initials if p else ''

    def get_target_user_name(self, obj):
        if not obj.target_user: return None
        p = getattr(obj.target_user, 'profile', None)
        return p.full_name if p else obj.target_user.email
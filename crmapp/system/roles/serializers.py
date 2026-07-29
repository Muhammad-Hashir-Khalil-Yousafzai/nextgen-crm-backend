# roles/serializers.py
from rest_framework import serializers
from .models import Role, Permission, RolePermission, UserRole, TemporaryAccess
from . import services


class RoleListSerializer(serializers.ModelSerializer):
    user_count = serializers.IntegerField(read_only=True)
    perm_count = serializers.SerializerMethodField()

    class Meta:
        model  = Role
        fields = ['id', 'slug', 'name', 'description', 'color_hex',
                  'level', 'is_system', 'user_count', 'perm_count', 'created_at']

    def get_perm_count(self, obj):
        return obj.permissions.filter(granted=True).count()


class RoleDetailSerializer(serializers.ModelSerializer):
    user_count = serializers.IntegerField(read_only=True)
    perms      = serializers.SerializerMethodField()

    class Meta:
        model  = Role
        fields = ['id', 'slug', 'name', 'description', 'color_hex',
                  'level', 'is_system', 'user_count', 'perms', 'created_at']

    def get_perms(self, obj):
        return services.get_role_permission_matrix(obj)


class RoleCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Role
        fields = ['name', 'description', 'color_hex', 'level']


class RolePermissionUpdateSerializer(serializers.Serializer):
    perms = serializers.DictField(child=serializers.DictField(child=serializers.BooleanField()))


class UserRoleSerializer(serializers.ModelSerializer):
    user_name     = serializers.SerializerMethodField()
    user_email    = serializers.CharField(source='user.email',    read_only=True)
    user_initials = serializers.SerializerMethodField()
    role_name     = serializers.CharField(source='role.name',     read_only=True)
    role_color    = serializers.CharField(source='role.color_hex', read_only=True)

    class Meta:
        model  = UserRole
        fields = ['id', 'user', 'user_name', 'user_email', 'user_initials',
                  'role', 'role_name', 'role_color', 'assigned_by', 'assigned_at', 'is_active']
        read_only_fields = ['id', 'assigned_at']

    def get_user_name(self, obj):
        p = getattr(obj.user, 'profile', None)
        return p.full_name if p else obj.user.email

    def get_user_initials(self, obj):
        p = getattr(obj.user, 'profile', None)
        return p.avatar_initials if p else ''


class TemporaryAccessSerializer(serializers.ModelSerializer):
    user_name  = serializers.SerializerMethodField()
    role_name  = serializers.CharField(source='role.name',       read_only=True)
    role_color = serializers.CharField(source='role.color_hex',  read_only=True)
    granter    = serializers.SerializerMethodField()

    class Meta:
        model  = TemporaryAccess
        fields = ['id', 'user', 'user_name', 'role', 'role_name', 'role_color',
                  'reason', 'granted_by', 'granter', 'granted_at', 'expires_at', 'is_active']
        read_only_fields = ['id', 'granted_at']

    def get_user_name(self, obj):
        p = getattr(obj.user, 'profile', None)
        return p.full_name if p else obj.user.email

    def get_granter(self, obj):
        if not obj.granted_by: return None
        p = getattr(obj.granted_by, 'profile', None)
        return p.full_name if p else obj.granted_by.email
# roles/views.py
from rest_framework import status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated

from .models import Role, UserRole, TemporaryAccess
from .serializers import (
    RoleListSerializer, RoleDetailSerializer, RoleCreateSerializer,
    RolePermissionUpdateSerializer, UserRoleSerializer, TemporaryAccessSerializer,
)
from . import services
from .permissions import can, get_user_permissions


class RoleViewSet(ModelViewSet):
    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'full_matrix']:
            return [can('settings', 'view')()]
        return [can('settings', 'edit')()]

    def get_serializer_class(self):
        if self.action == 'list':               return RoleListSerializer
        if self.action == 'create':             return RoleCreateSerializer
        if self.action == 'update_permissions': return RolePermissionUpdateSerializer
        return RoleDetailSerializer

    def get_queryset(self):
        return services.get_all_roles(actor=self.request.user)

    def create(self, request, *args, **kwargs):
        s = RoleCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        role = services.create_role(actor=request.user, **s.validated_data)
        return Response(RoleDetailSerializer(role).data, status=status.HTTP_201_CREATED)

    # ✅ FIX: PATCH /roles/5/ mein perms bhi handle karo
    def partial_update(self, request, *args, **kwargs):
        role = self.get_object()
        if 'perms' in request.data:
            s = RolePermissionUpdateSerializer(data=request.data)
            s.is_valid(raise_exception=True)
            services.update_role_permissions(role, s.validated_data['perms'], actor=request.user)
            return Response(RoleDetailSerializer(role).data)
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        role = self.get_object()
        try:
            services.delete_role(role, actor=request.user)
        except Exception as e:
            return Response({'detail': str(e)}, status=400)
        return Response({'detail': 'Role deleted.'})

    @action(detail=True, methods=['patch'], url_path='permissions')
    def update_permissions(self, request, pk=None):
        role = self.get_object()
        s    = RolePermissionUpdateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.update_role_permissions(role, s.validated_data['perms'], actor=request.user)
        return Response(RoleDetailSerializer(role).data)

    @action(detail=True, methods=['post'], url_path='clone')
    def clone(self, request, pk=None):
        role     = self.get_object()
        new_role = services.clone_role(role, actor=request.user)
        return Response(RoleDetailSerializer(new_role).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='matrix')
    def full_matrix(self, request):
        roles = services.get_all_roles(actor=request.user)
        return Response([{
            'id': r.id, 'slug': r.slug, 'name': r.name,
            'color_hex': r.color_hex, 'level': r.level,
            'user_count': r.user_count,
            'perms': services.get_role_permission_matrix(r),
        } for r in roles])


class UserRoleViewSet(ModelViewSet):
    serializer_class   = UserRoleSerializer
    permission_classes = [can('settings', 'edit')]
    queryset           = UserRole.objects.select_related(
        'user', 'user__profile', 'role', 'assigned_by'
    ).filter(is_active=True)

    def create(self, request, *args, **kwargs):
        from django.contrib.auth.models import User as AuthUser
        user_id = request.data.get('user')
        role_id = request.data.get('role')
        if not user_id or not role_id:
            return Response({'detail': 'user and role required.'}, status=400)
        try:
            user = AuthUser.objects.get(pk=user_id)
        except AuthUser.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=404)
        ur = services.assign_role_to_user(user, role_id, assigned_by=request.user)
        return Response(UserRoleSerializer(ur).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        ur = self.get_object()
        services.revoke_role_from_user(ur.user, ur.role_id, actor=request.user)
        return Response({'detail': 'Role revoked.'})


class TemporaryAccessViewSet(ModelViewSet):
    serializer_class   = TemporaryAccessSerializer
    permission_classes = [can('settings', 'edit')]
    queryset           = TemporaryAccess.objects.select_related(
        'user', 'user__profile', 'role', 'granted_by'
    ).filter(is_active=True).order_by('expires_at')

    def create(self, request, *args, **kwargs):
        from django.contrib.auth.models import User as AuthUser
        user_id    = request.data.get('user')
        role_id    = request.data.get('role')
        reason     = request.data.get('reason', '')
        expires_at = request.data.get('expires_at')
        if not all([user_id, role_id, expires_at]):
            return Response({'detail': 'user, role, expires_at required.'}, status=400)
        try:
            user = AuthUser.objects.get(pk=user_id)
        except AuthUser.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=404)
        ta = services.grant_temporary_access(
            user=user, role_id=role_id, reason=reason,
            expires_at=expires_at, granted_by=request.user
        )
        return Response(TemporaryAccessSerializer(ta).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        ta = self.get_object()
        services.revoke_temporary_access(ta, actor=request.user)
        return Response({'detail': 'Temporary access revoked.'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_permissions(request):
    """GET /api/me/permissions/ — called by React on login."""
    perms = get_user_permissions(request.user)
    roles = list(request.user.user_roles.filter(
        is_active=True
    ).values_list('role__slug', flat=True))
    p = getattr(request.user, 'profile', None)
    return Response({
        'user_id':   request.user.id,
        'full_name': p.full_name if p else request.user.get_full_name(),
        'email':     request.user.email,
        'roles':     roles,
        'permissions': perms,
    })